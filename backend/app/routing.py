"""Export-driven directed route cache, shortest returned alternative, no traffic."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener

from app.geocoding import fingerprint, token_value, NoRedirect
from app.importers.reference import norm
from app.matching import configuration_digest
from app.distances import display_route

POLICY = 'mapbox-v5-shortest-returned-no-traffic-v1'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS route_distances(
 id INTEGER PRIMARY KEY, cache_key TEXT NOT NULL UNIQUE, profile TEXT NOT NULL,
 origin_hash TEXT NOT NULL, destination_hash TEXT NOT NULL,
 origin_geocode_id INTEGER NOT NULL, destination_geocode_id INTEGER NOT NULL,
 policy TEXT NOT NULL, status TEXT NOT NULL, meters TEXT, kms TEXT,
 requested_at TEXT NOT NULL, completed_at TEXT, alternatives_count INTEGER,
 message TEXT, permission_basis TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS route_visualizations(
 route_id INTEGER PRIMARY KEY REFERENCES route_distances(id), status TEXT NOT NULL,
 geometry TEXT, kms TEXT, requested_at TEXT NOT NULL, message TEXT);
CREATE TABLE IF NOT EXISTS route_saved_contexts(
 route_id INTEGER PRIMARY KEY REFERENCES route_distances(id), contexts TEXT NOT NULL);
'''


def profile(mode):
    return {'auto':'driving','privé auto':'driving','fiets':'cycling'}.get(norm(mode))


def effective(rows, day):
    eligible = [row for row in rows if row['valid_from'] <= day]
    return max(eligible, key=lambda row: (row['valid_from'], row['id'])) if eligible else None


def coords(geocode):
    if not geocode or geocode['status'] not in ('CONFIRMED', 'REVIEW'):
        raise ValueError('Coördinaten ontbreken of zijn afgewezen.')
    r = json.loads(geocode['result'])
    if r.get('automatic_review_required') and geocode['status']!='CONFIRMED':raise ValueError('Automatische adresmatch onvoldoende zeker; corrigeer of controleer het adres.')
    values = (r.get('longitude'), r.get('latitude'))
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in values) or not (-180 <= values[0] <= 180 and -90 <= values[1] <= 90):
        raise ValueError('Ongeldige coördinaten.')
    return values


def plan(db, config, run_id):
    selected = db.execute('SELECT payload FROM matching_runs WHERE id=?', (run_id,)).fetchone()
    if not selected:
        raise ValueError('Selecteer een opgeslagen exportverwerking.')
    seed = json.loads(selected['payload']); source = seed['source_sha256']
    excluded_months={r['month'] for r in db.execute('SELECT month FROM excluded_months')}
    if seed['month'] in excluded_months:raise ValueError('Deze maand is uitgesloten van verwerking.')
    months = {}
    # Latest snapshot per month for this exact uploaded source.
    for row in db.execute('SELECT payload FROM matching_runs ORDER BY id DESC'):
        payload = json.loads(row['payload'])
        if payload['month'] in excluded_months:continue
        if payload.get('source_sha256') == source and payload['month'] not in months:
            months[payload['month']] = payload
    if any(p['configuration_digest'] != configuration_digest(config) for p in months.values()):
        raise ValueError('Vernieuw eerst de maandshiften: exportkoppelingen of tarieven zijn gewijzigd.')
    workers = {r['id']:r['name'] for r in config['workers']}
    homes = [dict(r) for r in db.execute('SELECT * FROM worker_addresses')]
    sites = [dict(r) for r in db.execute('SELECT * FROM location_address_versions')]
    geocodes = {r['address_hash']:dict(r) for r in db.execute('SELECT * FROM address_geocodes')}
    from app.route_corrections import cached_distances
    cached = {r['cache_key']:r for r in cached_distances(db)}
    needed = {}; blocked = []; excluded = 0
    for payload in months.values():
        from app.shift_transport import choices as transport_choices
        overrides=transport_choices(db,payload)
        from app.itinerary import itineraries
        journey=itineraries(payload)
        agents = {a['planet_id']:a for a in payload['agents']}
        for movement in payload['movements']:
            agent = agents[movement['planet_id']]; wid = agent.get('worker_id'); day = movement['day']
            context = {'worker':workers.get(wid, movement['planet_id']), 'location':movement.get('location') or movement['source_location'], 'day':day}
            leg=journey.get((movement['planet_id'],day,movement.get('id')),{})
            if leg.get('error'):
                blocked.append({**context,'reason':leg['error']});continue
            from_location=leg.get('origin_location')
            if movement['status'] != 'MATCHED':
                blocked.append({**context,'reason':'Werknemer/locatie niet gekoppeld.'});continue
            routes = movement.get('routes', [])
            choice=overrides.get(movement.get('id'))
            if choice and choice['mode']!='DEFAULT':
                routes=({'AUTO':'Privé auto','BIKE':'Fiets','TRAIN':'Trein'}[choice['mode']],)
                routes=[{'mode':routes[0]}]
            if not routes:
                blocked.append({**context,'reason':'Geen vervoerswijze geldig op de prestatiedatum.'});continue
            for route in routes:
                if from_location and any(profile(r['mode'])=='driving' for r in routes) and profile(route['mode'])!='driving':continue
                mode = profile(route['mode'])
                if mode is None:
                    if norm(route['mode']) in ('trein','dienstwagen','mob budget'):
                        excluded += 1
                    else:
                        blocked.append({**context,'reason':'Onbekende vervoerswijze: '+route['mode']})
                    continue
                home = effective([r for r in homes if r['worker_id']==wid],day)
                if from_location:home=effective([r for r in sites if r['location_key']==norm(from_location)],day)
                site = effective([r for r in sites if r['location_key']==norm(movement['location'])],day)
                if not home or not site:
                    blocked.append({**context,'reason':'Woonadres of locatieadres ontbreekt op prestatiedatum.'});continue
                origin_hash = fingerprint(json.loads(home['address'])); destination_hash = fingerprint(json.loads(site['address']))
                origin = geocodes.get(origin_hash); destination = geocodes.get(destination_hash)
                try:
                    if not from_location and origin and origin['status'] != 'CONFIRMED':
                        raise ValueError('Wooncoördinaten nog niet bevestigd.')
                    coords(origin);coords(destination)
                except ValueError as error:
                    blocked.append({**context,'reason':str(error)});continue
                # Concrete geocodes, direction and policy matter as well as address/mode.
                key = sha256(json.dumps([POLICY,origin_hash,destination_hash,origin['id'],destination['id'],mode]).encode()).hexdigest()
                item = needed.setdefault(key,{'cache_key':key,'profile':mode,'origin_hash':origin_hash,'destination_hash':destination_hash,
                    'origin_geocode_id':origin['id'],'destination_geocode_id':destination['id'],
                    'contexts':[], 'cached':cached.get(key)})
                ref = {**context,'worker_id':wid,'mode':route['mode'],'home_valid_from':home['valid_from'],'location_valid_from':site['valid_from']}
                ref.update(origin_location=from_location,route_kind='TRANSFER' if from_location else 'HOME',multi_location=leg.get('multi_location',False))
                if ref not in item['contexts']:item['contexts'].append(ref)
    return {'source_sha256':source,'months':sorted(months),'routes':list(needed.values()),'blocked':blocked,
            'excluded':excluded,'new_requests':sum(not r['cached'] for r in needed.values())}


def parse_response(payload):
    if payload.get('code') != 'Ok' or not payload.get('routes'):
        raise ValueError('Mapbox heeft geen rijbare route gevonden.')
    distances = []
    try:
        for route in payload['routes']:
            raw = route['distance']
            if type(raw) not in (int,float):raise ValueError
            value = Decimal(str(raw))
            if not value.is_finite() or value < 0:raise ValueError
            distances.append(value)
    except (KeyError,TypeError,InvalidOperation,ValueError):
        raise ValueError('Ongeldige routeafstand ontvangen.') from None
    meters = min(distances)
    result = {'meters':str(meters),'kms':str(meters/Decimal(1000)), 'alternatives_count':len(distances)}
    geometry = payload['routes'][distances.index(meters)].get('geometry')
    if geometry is not None:
        validate_geometry(geometry)
        result['geometry'] = geometry
    return result


def validate_geometry(geometry):
    points = geometry.get('coordinates') if isinstance(geometry, dict) else None
    if not isinstance(geometry, dict) or geometry.get('type') != 'LineString' or not isinstance(points, list) or not 2 <= len(points) <= 50000:
        raise ValueError('Ongeldige routelijn ontvangen.')
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point) or not (-180 <= point[0] <= 180 and -85 <= point[1] <= 85):
            raise ValueError('Ongeldige routecoördinaten ontvangen.')


def request_distance(mode, origin, destination):
    if mode not in ('driving','cycling'):raise ValueError('Ongeldig routeprofiel.')
    coordinates = ';'.join(','.join(str(n) for n in point) for point in (origin,destination))
    query = urlencode({'access_token':token_value(),'alternatives':'true','overview':'full','geometries':'geojson','steps':'false'})
    url = f'https://api.mapbox.com/directions/v5/mapbox/{mode}/{coordinates}?{query}'
    try:
        with build_opener(NoRedirect()).open(url,timeout=20) as response:
            content=response.read(1_000_001)
        if len(content)>1_000_000:raise ValueError('Mapbox-respons te groot.')
        result = parse_response(json.loads(content))
        if 'geometry' not in result:raise ValueError('Mapbox heeft geen routelijn teruggegeven.')
        return result
    except HTTPError as error:
        raise ValueError(f'Mapbox-routeaanvraag geweigerd (HTTP {error.code}). Geen automatische herhaling.') from None
    except (URLError,TimeoutError,OSError):
        raise ValueError('Routeaanvraag onderbroken; kan al verwerkt/gefactureerd zijn. Geen automatische herhaling.') from None
    except (json.JSONDecodeError,TypeError,AttributeError):
        raise ValueError('Ongeldige Mapbox-respons. Geen automatische herhaling.') from None


def request_one(store, data, revision):
    if data.get('consent') is not True:
        raise ValueError('Bevestig toestemming voor aanvragen en blijvend opslaan van routeafstanden.')
    token_value()
    with store.transaction(revision) as db:
        current = plan(db,store.matching_config(db),data.get('run_id'))
        route = next((r for r in current['routes'] if r['cache_key']==data.get('cache_key')),None)
        if not route:raise ValueError('Routeplan gewijzigd. Vernieuw het plan.')
        if route['cached']:return
        origin = dict(db.execute('SELECT * FROM address_geocodes WHERE id=?',(route['origin_geocode_id'],)).fetchone())
        destination = dict(db.execute('SELECT * FROM address_geocodes WHERE id=?',(route['destination_geocode_id'],)).fetchone())
        now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO route_distances(cache_key,profile,origin_hash,destination_hash,origin_geocode_id,destination_geocode_id,policy,status,requested_at,permission_basis) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (route['cache_key'],route['profile'],route['origin_hash'],route['destination_hash'],origin['id'],destination['id'],POLICY,'PENDING',now,'Gebruiker bevestigt verkregen toestemming voor één aanvraag en permanente opslag'))
        rid=db.execute('SELECT id FROM route_distances WHERE cache_key=?',(route['cache_key'],)).fetchone()[0]
        db.execute('INSERT INTO route_saved_contexts VALUES(?,?)',(rid,json.dumps(route['contexts'])))
    # Commit intent before external request: crash/timeout never silently duplicates a call.
    try:
        result=request_distance(route['profile'],coords(origin),coords(destination));status='READY';message=None
    except ValueError as error:
        result={};status='ERROR';message=str(error)
    with store.transaction() as db:
        db.execute('UPDATE route_distances SET status=?,meters=?,kms=?,alternatives_count=?,completed_at=?,message=? WHERE cache_key=?',
                   (status,result.get('meters'),result.get('kms'),result.get('alternatives_count'),datetime.now(timezone.utc).isoformat(),message,route['cache_key']))
        if result.get('geometry'):
            rid = db.execute('SELECT id FROM route_distances WHERE cache_key=?', (route['cache_key'],)).fetchone()[0]
            db.execute('INSERT INTO route_visualizations VALUES(?,?,?,?,?,?)', (rid,'READY',json.dumps(result['geometry']),result['kms'],datetime.now(timezone.utc).isoformat(),None))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (datetime.now(timezone.utc).isoformat(),'Vaste Mapbox-routeafstand',json.dumps({'action':'route_distance_request','cache_key':route['cache_key'],'status':status})))


def request_visualization(store, data, revision):
    if data.get('consent') is not True:raise ValueError('Bevestig de eenmalige aanvullende routeaanvraag.')
    with store.transaction(revision) as db:
        route = db.execute('SELECT * FROM route_distances WHERE id=? AND status=?', (data.get('route_id'),'READY')).fetchone()
        if not route:raise ValueError('Geen opgeslagen routeafstand beschikbaar.')
        if db.execute('SELECT 1 FROM route_visualizations WHERE route_id=?', (route['id'],)).fetchone():return
        token_value()
        origin = coords(dict(db.execute('SELECT * FROM address_geocodes WHERE id=?', (route['origin_geocode_id'],)).fetchone()))
        destination = coords(dict(db.execute('SELECT * FROM address_geocodes WHERE id=?', (route['destination_geocode_id'],)).fetchone()))
        db.execute('INSERT INTO route_visualizations(route_id,status,requested_at) VALUES(?,?,?)', (route['id'],'PENDING',datetime.now(timezone.utc).isoformat()))
    try:
        result = request_distance(route['profile'],origin,destination)
        validate_geometry(result.get('geometry'))
        status,message = 'READY',None
    except ValueError as error:
        result = {};status,message = 'ERROR',str(error)
    with store.transaction() as db:
        db.execute('UPDATE route_visualizations SET status=?,geometry=?,kms=?,message=? WHERE route_id=?',
                   (status,json.dumps(result['geometry']) if result.get('geometry') else None,result.get('kms'),message,route['id']))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (datetime.now(timezone.utc).isoformat(),'Eenmalige aanvullende routelijn; oorspronkelijke km behouden',json.dumps({'route_id':route['id'],'status':status})))
