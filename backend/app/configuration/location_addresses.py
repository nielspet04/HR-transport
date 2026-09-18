"""Dated addresses for existing physical locations, not duplicate customers."""
from datetime import date, datetime, timezone
import json
from pathlib import Path

from app.cleaning.locations import load_location_rules
from app.importers.reference import norm
from .store import required, valid_day

SCHEMA = '''
CREATE TABLE IF NOT EXISTS location_address_versions(
 id INTEGER PRIMARY KEY, location_key TEXT NOT NULL, location TEXT NOT NULL,
 valid_from TEXT NOT NULL, address TEXT NOT NULL,
 changed_at TEXT NOT NULL, reason TEXT NOT NULL);
'''


def catalog(db):
    """Read existing route locations and confirmed customer mappings."""
    locations = {}
    def add(location, customer=None):
        key = norm(location)
        item = locations.setdefault(key, {'key': key, 'name': location, 'customers': set()})
        if customer:
            item['customers'].add(customer)
    for row in db.execute('SELECT location FROM routes ORDER BY id'):
        add(row['location'])
    for row in db.execute('SELECT customer,location FROM matching_location_links ORDER BY customer'):
        add(row['location'], row['customer'])
    path = Path(__file__).resolve().parents[3] / 'config/locations.toml'
    _, rules = load_location_rules(path)
    for rule in rules:
        add(rule.location, rule.customer)
    # Keep saved location addresses visible if a route is later retired.
    for row in db.execute('SELECT location FROM location_address_versions ORDER BY id'):
        add(row['location'])
    return [{**item, 'customers': sorted(item['customers'])} for item in
            sorted(locations.values(), key=lambda item: item['name'].casefold())]


def snapshot(db):
    from app.geocoding import enrich, fingerprint
    data = {'physical_locations': catalog(db),
            'location_addresses': [{**dict(row), 'address': json.loads(row['address'])}
                                   for row in db.execute('SELECT * FROM location_address_versions ORDER BY valid_from,id')]}
    enrich(db, data['location_addresses'])
    latest = {}
    for row in data['location_addresses']:
        if row['valid_from'] <= date.today().isoformat():
            latest[row['location_key']] = row
    ids = []; seen = set()
    for row in latest.values():
        digest = fingerprint(row['address'])
        if not row['geocode'] and row['address']['country'] == 'BE' and digest not in seen:
            ids.append(row['id']); seen.add(digest)
    data['location_geocoding_plan'] = {'address_ids': ids, 'requests': len(ids),
        'missing_addresses': sum(loc['key'] not in latest for loc in data['physical_locations']),
        'unsupported_country': sum(row['address']['country'] != 'BE' for row in latest.values())}
    return data


def geocode(store, data, revision):
    from app import geocoding
    with store.transaction(revision) as db:
        address_id = data.get('address_id')
        if type(address_id) is not int:
            raise ValueError('Kies een locatieadres.')
        row = db.execute('SELECT * FROM location_address_versions WHERE id=?', (address_id,)).fetchone()
        if not row:
            raise ValueError('Onbekend locatieadres.')
        current = db.execute('SELECT id FROM location_address_versions WHERE location_key=? AND valid_from<=? ORDER BY valid_from DESC,id DESC LIMIT 1',
                             (row['location_key'], date.today().isoformat())).fetchone()
        if not current or current['id'] != address_id:
            raise ValueError('Locatieadres is niet meer actueel. Vernieuw de lijst.')
        address = json.loads(row['address']); digest = geocoding.fingerprint(address)
        if db.execute('SELECT 1 FROM address_geocodes WHERE address_hash=?', (digest,)).fetchone():
            return  # Shared permanent address cache; never re-request failures silently.
        if data.get('consent') is not True:
            raise ValueError('Bevestig permanente Mapbox-geocodering voor de locatieadressen.')
        if address['country'] != 'BE':
            raise ValueError('Deze koppeling ondersteunt voorlopig uitsluitend België.')
        geocoding.token_value()
        try:
            result = geocoding.request_address(address)
        except ValueError as error:
            result = {'status': 'ERROR', 'message': str(error)}
        now = datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at) VALUES(?,?,?,?,?)',
                   (digest, 'mapbox-v6-permanent', result['status'], json.dumps(result), now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (now, 'Permanente locatiegeocodering op verzoek HR', json.dumps({'action': 'location_geocode', 'location_address_id': address_id})))


def save(db, data):
    key = norm(required(data.get('location')))
    known = {item['key']: item for item in catalog(db)}
    if key not in known:
        raise ValueError('Kies een bestaande fysieke locatie uit de lijst.')
    start = valid_day(data.get('valid_from'))
    reason = required(data.get('reason'))
    address = data.get('address')
    if not isinstance(address, dict):
        raise ValueError('Vul een adres in.')
    cleaned = {field: required(address.get(field)) for field in ('street', 'number', 'postal_code', 'city', 'country')}
    unit = address.get('unit', '')
    cleaned['unit'] = required(unit) if unit else ''
    country = cleaned['country'].upper()
    if len(country) != 2 or not country.isascii() or not country.isalpha():
        raise ValueError('Land vereist een tweelettercode, bijvoorbeeld BE.')
    cleaned['country'] = country
    last = db.execute('SELECT max(valid_from) FROM location_address_versions WHERE location_key=?', (key,)).fetchone()[0]
    if last and start < last:
        raise ValueError('Kies de laatste adresdatum of een latere datum; historiek blijft bewaard.')
    now = datetime.now(timezone.utc).isoformat()
    version_id = db.execute('INSERT INTO location_address_versions(location_key,location,valid_from,address,changed_at,reason) VALUES(?,?,?,?,?,?)',
                            (key, known[key]['name'], start, json.dumps(cleaned, ensure_ascii=False), now, reason)).lastrowid
    db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
               (now, reason, json.dumps({'action': 'location_address_save', 'location_key': key, 'version_id': version_id})))
    return version_id
