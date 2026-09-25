"""Stored route geometry and server-side Mapbox background; no browser access token."""
import json
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import build_opener
from urllib.error import HTTPError, URLError
from app.geocoding import NoRedirect, token_value
from app.routing import validate_geometry, profile
from app.distances import whole_kms
from app.geocoding import fingerprint
from app.importers.reference import norm

STATIC_IMAGE_MONTHLY_LIMIT = 1000
STATIC_IMAGE_CACHE_HOURS = 12


def catalog(db):
    """Public-safe links between stored routes and their HR contexts.

    Geometry and address hashes deliberately stay behind the preview endpoint.
    Repeated shift contexts are collapsed so the dashboard stays compact.
    """
    visuals = {row['route_id']: row['status'] for row in db.execute('SELECT route_id,status FROM route_visualizations')}
    workers_by_hash = {}
    for row in db.execute('SELECT worker_id,address FROM worker_addresses'):
        try: workers_by_hash.setdefault(fingerprint(json.loads(row['address'])), set()).add(row['worker_id'])
        except (json.JSONDecodeError, TypeError, ValueError): continue
    locations_by_hash = {}
    for row in db.execute('SELECT location_key,location,address FROM location_address_versions'):
        try: locations_by_hash.setdefault(fingerprint(json.loads(row['address'])), {})[row['location_key']] = row['location']
        except (json.JSONDecodeError, TypeError, ValueError): continue
    configured_routes = [dict(row) for row in db.execute('SELECT worker_id,location,location_key,mode FROM routes')]
    result = []
    seen = set()
    rows = db.execute('''SELECT d.id,d.profile,d.status,d.kms,d.origin_hash,d.destination_hash,c.contexts
                         FROM route_distances d
                         LEFT JOIN route_saved_contexts c ON c.route_id=d.id
                         WHERE d.status='READY'
                         ORDER BY d.id''')
    for row in rows:
        try:
            contexts = json.loads(row['contexts']) if row['contexts'] else []
        except (json.JSONDecodeError, TypeError):
            contexts = []
        # Old cached routes predate saved contexts. Reconnect them locally via
        # address fingerprints plus the explicit employee/location route table.
        for worker_id in workers_by_hash.get(row['origin_hash'], ()):
            for location_key, location in locations_by_hash.get(row['destination_hash'], {}).items():
                for configured in configured_routes:
                    if configured['worker_id'] == worker_id and configured['location_key'] == location_key and profile(configured['mode']) == row['profile']:
                        inferred = {'worker_id': worker_id, 'location': location, 'mode': configured['mode'], 'route_kind': 'HOME'}
                        if inferred not in contexts: contexts.append(inferred)
        for context in contexts if isinstance(contexts, list) else []:
            if not isinstance(context, dict) or type(context.get('worker_id')) is not int:
                continue
            key = (row['id'], context['worker_id'], norm(context.get('location')), norm(context.get('mode')))
            if key in seen:
                continue
            seen.add(key)
            result.append({
                'route_id': row['id'], 'worker_id': context['worker_id'],
                'location': context.get('location') or '', 'location_key': norm(context.get('location')),
                'mode': context.get('mode') or row['profile'], 'profile': row['profile'],
                'kms': str(whole_kms(row['kms'])), 'visual_status': visuals.get(row['id'], 'MISSING'),
                'route_kind': context.get('route_kind', 'HOME'),
                'origin_location': context.get('origin_location')
            })
    return result


def preview(store, route_id):
    with store.connect() as db:
        row = db.execute('SELECT v.*,d.kms AS original_kms FROM route_visualizations v JOIN route_distances d ON d.id=v.route_id WHERE v.route_id=?', (route_id,)).fetchone()
    if not row:return {'status':'MISSING'}
    result = dict(row)
    for key in ('kms','original_kms'):
        if result.get(key) is not None:result[key]=str(whole_kms(result[key]))
    if row['status'] != 'READY':return result
    geometry = json.loads(row['geometry']);validate_geometry(geometry)
    points = [( (lon+180)/360, (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2 ) for lon,lat in geometry['coordinates']]
    xs,ys = zip(*points);cx,cy = (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
    zoom = round(max(0,min(18,math.log2(800/(512*max(max(xs)-min(xs),1e-9))),math.log2(480/(512*max(max(ys)-min(ys),1e-9))))),2)
    scale = 512*2**zoom
    result.update(points=[[450+(x-cx)*scale,300+(y-cy)*scale] for x,y in points],
                  center=[cx*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*cy))))],zoom=zoom)
    result.pop('geometry')
    return result


def background(store, route_id):
    item = preview(store,route_id)
    if item['status'] != 'READY':raise ValueError('Geen routelijn beschikbaar.')
    now = datetime.now(timezone.utc)
    with store.connect() as db:
        cached = db.execute('SELECT * FROM route_map_backgrounds WHERE route_id=?', (route_id,)).fetchone()
        if cached and cached['status'] == 'READY' and cached['png'] and cached['expires_at'] > now.isoformat():
            return bytes(cached['png'])
        if cached and cached['status'] == 'PENDING':
            raise ValueError('Kaartachtergrond wordt al opgehaald. Probeer zo meteen opnieuw.')
        month = now.strftime('%Y-%m')
        used = db.execute('SELECT requests FROM route_map_usage WHERE month=?', (month,)).fetchone()
        if used and used['requests'] >= STATIC_IMAGE_MONTHLY_LIMIT:
            raise ValueError('Veilige maandlimiet voor kaartachtergronden bereikt; de routelijn blijft zichtbaar zonder achtergrond.')
        db.execute('INSERT INTO route_map_usage(month,requests) VALUES(?,1) ON CONFLICT(month) DO UPDATE SET requests=requests+1', (month,))
        expires = (now + timedelta(hours=STATIC_IMAGE_CACHE_HOURS)).isoformat()
        db.execute('INSERT INTO route_map_backgrounds(route_id,status,png,requested_at,expires_at,message) VALUES(?,?,?,?,?,NULL) ON CONFLICT(route_id) DO UPDATE SET status=excluded.status,png=NULL,requested_at=excluded.requested_at,expires_at=excluded.expires_at,message=NULL',
                   (route_id,'PENDING',None,now.isoformat(),expires))
        db.commit()
    lon,lat = item['center']
    url = f'https://api.mapbox.com/styles/v1/mapbox/streets-v12/static/{lon},{lat},{item["zoom"]},0/900x600?'+urlencode({'access_token':token_value()})
    try:
        with build_opener(NoRedirect()).open(url,timeout=20) as response:
            content = response.read(5_000_001)
        if len(content)>5_000_000 or not content.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Ongeldige kaartafbeelding.')
        with store.connect() as db:
            db.execute('UPDATE route_map_backgrounds SET status=?,png=?,message=NULL WHERE route_id=?', ('READY',content,route_id));db.commit()
        return content
    except (HTTPError,URLError,TimeoutError,OSError):
        with store.connect() as db:
            db.execute('UPDATE route_map_backgrounds SET status=?,message=? WHERE route_id=?', ('ERROR','Mapbox-kaartachtergrond niet beschikbaar.',route_id));db.commit()
        raise ValueError('Kaartachtergrond niet beschikbaar. Controleer Mapbox-token en rechten voor kaartafbeeldingen.') from None
