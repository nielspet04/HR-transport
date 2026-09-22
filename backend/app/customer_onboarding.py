"""Atomic onboarding for a previously unseen customer/work location."""
from datetime import datetime, timezone
import json

from app.configuration.location_addresses import catalog, save as save_location_address
from app.configuration.store import required, valid_day
from app.importers.reference import norm
from app.matching import key


def _context(payload, source_location):
    source_key = norm(source_location)
    source_rows = [row for row in payload['locations']
        if row['status'] == 'UNMATCHED_LOCATION' and norm(row['physical_location']) == source_key]
    movements = [movement for movement in payload['movements']
        if movement.get('location_status') == 'UNMATCHED_LOCATION' and norm(movement['source_location']) == source_key]
    if not source_rows or not movements:
        raise ValueError('Deze klantlocatie is niet meer ongekoppeld. Vernieuw het scherm.')
    return source_rows, movements


def onboard(store, data, revision):
    run_id = data.get('run_id')
    if type(run_id) is not int:
        raise ValueError('Selecteer een onbekende klant uit een maandverwerking.')
    source_location = required(data.get('source_location')); choice = data.get('choice')
    if choice not in ('EXISTING', 'NEW'):
        raise ValueError('Kies een bestaande of nieuwe fysieke werklocatie.')
    with store.transaction(revision) as db:
        run = db.execute('SELECT * FROM matching_runs WHERE id=?', (run_id,)).fetchone()
        if not run:
            raise ValueError('De geselecteerde maandverwerking bestaat niet meer.')
        payload = json.loads(run['payload']); locations, movements = _context(payload, source_location)
        first_day = min(movement['day'] for movement in movements)
        start = valid_day(data.get('valid_from'))
        if start > first_day:
            raise ValueError('De locatie moet uiterlijk op de eerste shiftdatum geldig zijn.')
        reason = required(data.get('reason'))
        known = {item['key']:item for item in catalog(db)}
        target = required(data.get('location')); target_key = norm(target)
        if choice == 'EXISTING':
            if target_key not in known:
                raise ValueError('Kies een bestaande fysieke locatie uit de lijst.')
            target = known[target_key]['name']
        elif target_key in known:
            raise ValueError('Deze fysieke locatie bestaat al. Kies bestaande locatie.')

        customers = sorted({row['customer'] for row in locations})
        for customer in customers:
            db.execute('''INSERT INTO matching_location_links(customer,location) VALUES(?,?)
                ON CONFLICT(customer) DO UPDATE SET location=excluded.location''', (key(customer), target))
        if choice == 'NEW':
            address = data.get('address')
            if not isinstance(address, dict) or not address.get('country'):
                raise ValueError('Vul het volledige locatieadres en de landcode in.')
            # The confirmed customer link makes the new physical location part of
            # the catalog before its first dated address is validated and saved.
            save_location_address(db, {'location':target,'valid_from':start,
                'address':address,'reason':reason})

        agents = {agent['planet_id']:agent for agent in payload['agents']}
        earliest = {}
        for movement in movements:
            worker_id = agents[movement['planet_id']].get('worker_id')
            if worker_id is None or agents[movement['planet_id']]['status'] != 'MATCHED':
                continue
            earliest[worker_id] = min(earliest.get(worker_id, movement['day']), movement['day'])
        now = datetime.now(timezone.utc).isoformat(); created_routes = []
        for worker_id, day in earliest.items():
            if db.execute('SELECT 1 FROM routes WHERE worker_id=? AND location_key=?',
                (worker_id, target_key)).fetchone():
                continue
            route_id = db.execute('''INSERT INTO routes(worker_id,location,location_key,mode,mode_key)
                VALUES(?,?,?,?,?)''', (worker_id,target,target_key,'Privé auto','privé auto')).lastrowid
            store.version(db,route_id,day,None,
                'Nieuwe klantlocatie uit Pl@net · standaard privéauto',allow_missing=True)
            db.execute('''INSERT INTO transport_defaults
                (worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)''',
                (worker_id,target,target_key,'Privé auto',day,reason,now))
            created_routes.append(route_id)
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'customer_onboard','source_location':source_location,
                'customers':[key(customer) for customer in customers],'location':target,
                'new_location':choice=='NEW','route_ids':created_routes})))
        results = store.process_matching_file(db,run['source_path'],payload['source_sha256'])
        return {'location':target,'customers':len(customers),'routes':len(created_routes),
            'months':len(results),'new_location':choice=='NEW'}
