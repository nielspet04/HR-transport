"""Atomic onboarding of a genuinely new employee found in a Planet export."""
from datetime import datetime, timezone
import json

from app.configuration.addresses import append_address
from app.configuration.external_references import append_reference
from app.configuration.store import required, valid_day
from app.importers.reference import norm
from app.matching import key
from app.transport_defaults import MODES


def _agent_context(payload, planet_id):
    agent = next((item for item in payload['agents'] if item['planet_id'] == planet_id), None)
    if not agent or agent['status'] != 'UNMATCHED_EMPLOYEE' or agent.get('worker_id') is not None:
        raise ValueError('Deze Pl@net-agent is niet meer een ongekoppelde nieuwe werknemer. Vernieuw het scherm.')
    movements = [movement for movement in payload['movements'] if movement['planet_id'] == planet_id]
    if not movements:
        raise ValueError('Voor deze nieuwe werknemer zijn geen behouden shiften gevonden.')
    return agent, movements


def _assignments(db, movements, supplied):
    if not isinstance(supplied, list) or not supplied or any(not isinstance(item, dict) for item in supplied):
        raise ValueError('Bevestig de werklocatie en het standaard vervoer.')
    by_source = {}
    for item in supplied:
        source = required(item.get('source_location'))
        if norm(source) in by_source:
            raise ValueError('Elke bronlocatie mag maar één keer voorkomen.')
        target = required(item.get('location')); mode = item.get('mode')
        if mode not in MODES:
            raise ValueError('Kies per locatie privéauto, fiets, trein, dienstwagen of mobiliteitsbudget.')
        canonical = db.execute('SELECT location FROM routes WHERE location_key=? ORDER BY id LIMIT 1', (norm(target),)).fetchone()
        if not canonical:
            raise ValueError('Kies een bestaande fysieke werklocatie. Voeg een volledig nieuwe locatie eerst toe bij Werklocaties.')
        by_source[norm(source)] = {'source_location': source, 'location': canonical['location'], 'mode': mode}
    expected = {norm(movement['source_location']) for movement in movements}
    if set(by_source) != expected:
        raise ValueError('Bevestig precies alle bronlocaties van deze werknemer.')
    for movement in movements:
        assignment = by_source[norm(movement['source_location'])]
        if movement.get('location') and norm(movement['location']) != norm(assignment['location']):
            raise ValueError('Een reeds bevestigde fysieke locatie mag niet via werknemersregistratie worden gewijzigd.')
    target_modes = {}
    for item in by_source.values():
        old = target_modes.setdefault(norm(item['location']), item['mode'])
        if old != item['mode']:
            raise ValueError('Kies voor dezelfde fysieke locatie één standaard vervoerswijze.')
    return by_source


def onboard(store, data, revision):
    run_id = data.get('run_id'); planet_id = data.get('planet_id')
    if type(run_id) is not int or not isinstance(planet_id, str):
        raise ValueError('Selecteer een nieuwe werknemer uit een maandverwerking.')
    with store.transaction(revision) as db:
        run = db.execute('SELECT * FROM matching_runs WHERE id=?', (run_id,)).fetchone()
        if not run:
            raise ValueError('De geselecteerde maandverwerking bestaat niet meer.')
        payload = json.loads(run['payload']); agent, movements = _agent_context(payload, planet_id)
        name = required(data.get('name')); name_key = norm(name)
        if db.execute('SELECT 1 FROM workers WHERE name_key=?', (name_key,)).fetchone():
            raise ValueError('Deze werknemersnaam bestaat al. Gebruik dan de bestaande naamkoppeling in plaats van een nieuw profiel.')
        source_keys = agent.get('source_keys') or []
        if name_key not in source_keys and name_key not in {norm(value) for value in agent.get('source_names', [])}:
            raise ValueError('De nieuwe profielnaam moet overeenkomen met de naam uit de Pl@net-export.')
        first_day = min(movement['day'] for movement in movements)
        start = valid_day(data.get('valid_from'))
        if start > first_day:
            raise ValueError('Adres en vervoer moeten uiterlijk op de eerste shiftdatum geldig zijn.')
        assignments = _assignments(db, movements, data.get('assignments'))
        reason = required(data.get('reason'))
        address = data.get('address')
        if not isinstance(address, dict) or not address.get('country'):
            raise ValueError('Vul het volledige woonadres en de landcode in.')

        worker_id = db.execute('INSERT INTO workers(name,name_key) VALUES(?,?)', (name, name_key)).lastrowid
        db.execute('INSERT INTO matching_employee_links(planet_id,worker_id,source_keys) VALUES(?,?,?)',
            (planet_id, worker_id, json.dumps(source_keys)))
        append_address(db, worker_id, start, address, reason)

        reference_candidates = db.execute('''SELECT c.*,i.valid_from FROM external_reference_candidates c
            JOIN external_reference_imports i ON i.hash=c.import_hash
            WHERE c.status='REVIEW' ORDER BY c.id''').fetchall()
        references = [row for row in reference_candidates if norm(row['name']) == name_key]
        if len(references) == 1:
            candidate = references[0]
            supplied_reference = data.get('external_reference')
            if supplied_reference not in (None, '', candidate['external_reference']):
                raise ValueError('Het vooraf gevonden loonnummer werd gewijzigd. Pas de bestaande bronregel afzonderlijk aan.')
            append_reference(db, worker_id, candidate['valid_from'], candidate['external_reference'], reason,
                candidate['source_row'], candidate['import_hash'])
            db.execute("UPDATE external_reference_candidates SET status='LINKED',worker_id=? WHERE id=?",
                (worker_id, candidate['id']))
            external_reference = candidate['external_reference']
        else:
            if len(references) > 1:
                raise ValueError('Meerdere loonreferentiebronregels hebben deze naam. Los die eerst op bij Woonadressen.')
            external_reference = data.get('external_reference')
            append_reference(db, worker_id, start, external_reference, reason)

        grouped = {}
        for movement in movements:
            assignment = assignments[norm(movement['source_location'])]
            earliest = min(item['day'] for item in movements
                if norm(assignments[norm(item['source_location'])]['location']) == norm(assignment['location']))
            grouped[norm(assignment['location'])] = (assignment['location'], assignment['mode'], earliest)
            if movement.get('location_status') != 'MATCHED':
                for shift in movement.get('source_shifts', []):
                    customer = key(shift['customer'])
                    db.execute('''INSERT INTO matching_location_links(customer,location) VALUES(?,?)
                        ON CONFLICT(customer) DO UPDATE SET location=excluded.location''',
                        (customer, assignment['location']))
        now = datetime.now(timezone.utc).isoformat()
        created_routes = []
        for location, mode, day in grouped.values():
            route_id = db.execute('''INSERT INTO routes(worker_id,location,location_key,mode,mode_key)
                VALUES(?,?,?,?,?)''', (worker_id, location, norm(location), mode, norm(mode))).lastrowid
            store.version(db, route_id, day, None,
                'Nieuwe werknemer via Pl@net · standaard vervoer bevestigd', allow_missing=True)
            db.execute('''INSERT INTO transport_defaults
                (worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)''',
                (worker_id, location, norm(location), mode, day, reason, now))
            created_routes.append(route_id)
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now, reason, json.dumps({'action':'employee_onboard','planet_id':planet_id,
                'worker_id':worker_id,'locations':[item[0] for item in grouped.values()],
                'route_ids':created_routes})))
        results = store.process_matching_file(db, run['source_path'], payload['source_sha256'])
        return {'worker_id':worker_id,'name':name,'external_reference':external_reference,
            'routes':len(created_routes),'months':len(results)}
