"""Permanent Mapbox geocoding only; routing and payroll remain separate."""
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler

SCHEMA = '''
CREATE TABLE IF NOT EXISTS address_geocodes(
 id INTEGER PRIMARY KEY, address_hash TEXT NOT NULL UNIQUE,
 provider TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL,
 requested_at TEXT NOT NULL, reviewed_at TEXT, reason TEXT);
'''
TOKEN_PATH = Path(__file__).resolve().parents[2] / 'data/state/mapbox-token'


def token_value():
    token = os.environ.get('MAPBOX_ACCESS_TOKEN', '').strip()
    if not token and TOKEN_PATH.exists():
        if TOKEN_PATH.stat().st_mode & 0o077:
            raise ValueError('Tokenbestand moet privé zijn (rechten 600).')
        token = TOKEN_PATH.read_text().strip()
    if not token or not token.startswith(('pk.', 'sk.')) or any(c.isspace() for c in token):
        raise ValueError('Stel eerst lokaal de Mapbox-token in met scripts/setup_mapbox.py.')
    return token


def configured():
    try:
        token_value()
        return True
    except (ValueError, OSError):
        return False


def fingerprint(address):
    # Preserve components, including bus; hash is not anonymisation.
    canonical = {k: ' '.join(str(address.get(k, '')).casefold().split())
                 for k in ('street', 'number', 'unit', 'postal_code', 'city', 'country')}
    return sha256(('mapbox-v6-permanent-v1:' + json.dumps(canonical, sort_keys=True)).encode()).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward address/token to another destination.


def request_address(address):
    if address.get('country') != 'BE':
        raise ValueError('Deze eerste koppeling ondersteunt uitsluitend bevestigde Belgische adressen.')
    params = {'access_token': token_value(), 'permanent': 'true', 'autocomplete': 'false',
              'types': 'address', 'limit': '1', 'country': 'be',
              'address_number': address['number'], 'street': address['street'],
              'postcode': address['postal_code'], 'place': address['city']}
    # Unit stays local: road access is at the building, not at an apartment.
    url = 'https://api.mapbox.com/search/geocode/v6/forward?' + urlencode(params)
    try:
        with build_opener(NoRedirect()).open(url, timeout=15) as response:
            content = response.read(1_000_001)
        if len(content) > 1_000_000:
            raise ValueError('Ongeldige Mapbox-respons.')
        return parse_response(json.loads(content))
    except HTTPError as error:
        # Never expose response body, URL, address or token in exception text.
        messages = {401: 'Mapbox-token geweigerd.', 403: 'Mapbox-toegang geweigerd; controleer token en permanente geocodering.',
                    429: 'Mapbox-limiet bereikt. Geen automatische herhaling.'}
        raise ValueError(messages.get(error.code, 'Mapbox-aanvraag mislukt. Geen automatische herhaling.')) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('Mapbox niet bereikbaar. Geen automatische herhaling; een timeout kan al gefactureerd zijn.') from None
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('Ongeldige Mapbox-respons.') from None


def parse_response(payload):
    features = payload.get('features')
    if not isinstance(features, list):
        raise ValueError('Ongeldige Mapbox-respons.')
    if not features:
        return {'status': 'NO_MATCH', 'message': 'Geen adres gevonden; controleer het bronadres.'}
    p = features[0].get('properties', {})
    coords = p.get('coordinates', {})
    lon, lat = coords.get('longitude'), coords.get('latitude')
    if p.get('feature_type') != 'address' or any(type(n) not in (int, float) or not math.isfinite(n) for n in (lon, lat)):
        raise ValueError('Mapbox gaf geen geldige adrescoördinaten.')
    country = p.get('context', {}).get('country', {}).get('country_code', '').upper()
    if country != 'BE' or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError('Mapbox gaf geen geldig Belgisch adres.')
    match = p.get('match_code', {})
    eligible = (coords.get('accuracy') in ('rooftop', 'parcel', 'point')
                and match.get('address_number') == 'matched' and match.get('street') == 'matched'
                and match.get('postcode') == 'matched' and match.get('confidence') in ('exact', 'high'))
    return {'status': 'REVIEW', 'longitude': lon, 'latitude': lat,
            'label': str(p.get('full_address') or (str(p.get('name', '')) + ', ' + str(p.get('place_formatted', ''))))[:500],
            'accuracy': coords.get('accuracy'), 'confidence': match.get('confidence'),
            'match': {k: match.get(k) for k in ('address_number', 'street', 'postcode', 'place', 'country')},
            'eligible': eligible,
            'message': 'Controleer het gevonden adres vóór bevestiging.' if eligible else 'Onvoldoende precieze adresmatch; corrigeer het bronadres.'}


def apply(store, action, data, revision):
    with store.transaction(revision) as db:
        address_id = data.get('address_id')
        if type(address_id) is not int:
            raise ValueError('Kies een opgeslagen adres.')
        row = db.execute('SELECT * FROM worker_addresses WHERE id=?', (address_id,)).fetchone()
        if not row:
            raise ValueError('Onbekend adres.')
        if action == 'address_geocode_bulk_item':
            current = db.execute('SELECT id FROM worker_addresses WHERE worker_id=? AND valid_from<=? ORDER BY valid_from DESC,id DESC LIMIT 1',
                                 (row['worker_id'], date.today().isoformat())).fetchone()
            if not current or current['id'] != address_id:
                raise ValueError('Adres gewijzigd of niet actueel. Bulkverwerking gestopt; vernieuw het plan.')
            action = 'address_geocode'
        address = json.loads(row['address']); digest = fingerprint(address)
        old = db.execute('SELECT * FROM address_geocodes WHERE address_hash=?', (digest,)).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if action == 'address_geocode':
            if old:
                return  # No implicit retry, including NO_MATCH/ERROR; prevents extra billing.
            if data.get('consent') is not True:
                raise ValueError('Bevestig verzending naar Mapbox en permanente geocodering.')
            token_value()  # Missing local config does not create a failed attempt.
            if address.get('country') != 'BE':
                raise ValueError('Bevestig eerst landcode BE.')
            try:
                result = request_address(address)
            except ValueError as error:
                result = {'status': 'ERROR', 'message': str(error)}
            db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at) VALUES(?,?,?,?,?)',
                       (digest, 'mapbox-v6-permanent', result['status'], json.dumps(result), now))
        elif action == 'geocode_review':
            if not old or old['status'] != 'REVIEW':
                raise ValueError('Dit resultaat staat niet meer ter controle.')
            from app.configuration.store import required
            reason = required(data.get('reason'))
            result = json.loads(old['result'])
            if type(data.get('accept')) is not bool:
                raise ValueError('Kies bevestigen of afwijzen.')
            if data['accept'] and not result.get('eligible') and data.get('confirm_uncertain') is not True:
                raise ValueError('Deze match is onvoldoende precies. Corrigeer het bronadres.')
            if data['accept']:
                import math
                lon=result.get('longitude');lat=result.get('latitude')
                if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lon,lat)) or not (-180<=lon<=180 and -90<=lat<=90):raise ValueError('Geen geldige coördinaten; corrigeer het adres.')
            db.execute('UPDATE address_geocodes SET status=?,reviewed_at=?,reason=? WHERE id=?',
                       ('CONFIRMED' if data['accept'] else 'REJECTED', now, reason, old['id']))
        else:
            raise ValueError('Onbekende geocodingactie.')
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (now, 'Mapbox-geocodering: ' + action, json.dumps({'action': action, 'address_id': address_id,'confirm_uncertain':data.get('confirm_uncertain') is True})))


def enrich(db, addresses):
    cached = {r['address_hash']: {**dict(r), 'result': json.loads(r['result'])}
              for r in db.execute('SELECT * FROM address_geocodes')}
    for row in addresses:
        geocode = cached.get(fingerprint(row['address']))
        row['geocode'] = geocode
        row['geocode_status'] = geocode['status'] if geocode else 'NOT_REQUESTED'


def review_many(store, data, revision):
    """Atomic human review of selected current addresses, never API calls."""
    from app.configuration.store import required
    ids = data.get('address_ids')
    if not isinstance(ids, list) or not ids or len(ids) > 500 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Selecteer één of meer geldige adresregels (maximaal 500).')
    if type(data.get('accept')) is not bool:
        raise ValueError('Kies bevestigen of afwijzen.')
    reason = required(data.get('reason'))
    with store.transaction(revision) as db:
        geocodes = {}
        for address_id in ids:
            address = db.execute('SELECT * FROM worker_addresses WHERE id=?', (address_id,)).fetchone()
            if not address:
                raise ValueError('Onbekend adres. Vernieuw de controlelijst.')
            current = db.execute('SELECT id FROM worker_addresses WHERE worker_id=? AND valid_from<=? ORDER BY valid_from DESC,id DESC LIMIT 1',
                                 (address['worker_id'], date.today().isoformat())).fetchone()
            if not current or current['id'] != address_id:
                raise ValueError('Adresversie gewijzigd. Vernieuw de controlelijst.')
            digest = fingerprint(json.loads(address['address']))
            geocode = db.execute('SELECT * FROM address_geocodes WHERE address_hash=?', (digest,)).fetchone()
            if not geocode or geocode['status'] != 'REVIEW':
                raise ValueError('Een geselecteerd resultaat staat niet meer ter controle. Vernieuw de lijst.')
            if data['accept'] and not json.loads(geocode['result']).get('eligible'):
                raise ValueError('Een geselecteerde match is onvoldoende precies. Er is niets bevestigd.')
            geocodes[geocode['id']] = geocode
        now = datetime.now(timezone.utc).isoformat()
        status = 'CONFIRMED' if data['accept'] else 'REJECTED'
        for geocode_id in geocodes:
            db.execute('UPDATE address_geocodes SET status=?,reviewed_at=?,reason=? WHERE id=?',
                       (status, now, reason, geocode_id))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (now, reason, json.dumps({'action': 'geocode_review_many', 'address_ids': ids,
                                            'geocode_ids': list(geocodes), 'status': status})))
    return {'addresses': len(ids), 'results': len(geocodes), 'status': status}


def bulk_plan(addresses, today=None):
    """Only currently effective, uncached BE addresses; one call per hash."""
    today = today or date.today().isoformat()
    latest = {}
    for row in sorted(addresses, key=lambda r: (r['valid_from'], r['id'])):
        if row['valid_from'] <= today:
            latest[row['worker_id']] = row
    seen = set()
    ids = []
    blocked = 0
    existing = 0
    for row in latest.values():
        if row.get('geocode'):
            existing += 1
            continue
        if row['address'].get('country') != 'BE':
            blocked += 1
            continue
        digest = fingerprint(row['address'])
        if digest not in seen:
            ids.append(row['id'])
            seen.add(digest)
    return {'address_ids': ids, 'requests': len(ids), 'existing_profiles': existing,
            'blocked_profiles': blocked, 'current_profiles': len(latest)}


def confirm_hand_checked_current(store, revision, *, user_confirmed, reason):
    """Explicit user review can override provider confidence, not missing coordinates."""
    from app.configuration.store import required
    if user_confirmed is not True:
        raise ValueError('Expliciete handmatige controle vereist.')
    reason = required(reason)
    report = {'confirmed_results': 0, 'confidence_overrides': 0, 'missing_profiles': 0}
    with store.transaction(revision) as db:
        latest = {}
        for row in db.execute('SELECT * FROM worker_addresses WHERE valid_from<=? ORDER BY valid_from,id', (date.today().isoformat(),)):
            latest[row['worker_id']] = dict(row)
        results = {}
        for address in latest.values():
            components = json.loads(address['address'])
            row = db.execute('SELECT * FROM address_geocodes WHERE address_hash=?', (fingerprint(components),)).fetchone()
            if row and row['status'] == 'CONFIRMED':
                continue
            if not row or row['status'] != 'REVIEW':
                report['missing_profiles'] += 1
                continue
            result = json.loads(row['result'])
            coords = (result.get('longitude'), result.get('latitude'))
            if components.get('country') != 'BE' or any(type(n) not in (int, float) or not math.isfinite(n) for n in coords) or not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90):
                raise ValueError('Ongeldige coördinaten: bevestiging gestopt zonder gedeeltelijke wijzigingen.')
            results[row['id']] = result
        now = datetime.now(timezone.utc).isoformat()
        for result_id, result in results.items():
            db.execute("UPDATE address_geocodes SET status='CONFIRMED',reviewed_at=?,reason=? WHERE id=?", (now, reason, result_id))
            report['confirmed_results'] += 1
            report['confidence_overrides'] += not result.get('eligible', False)
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (now, reason, json.dumps({'action': 'geocode_manual_confirmation', 'geocode_ids': list(results), **report})))
    return report
