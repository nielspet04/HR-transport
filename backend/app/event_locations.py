"""Resolve one Event ad hoc source shift without creating a global customer link."""
from datetime import datetime, timezone
import json

from app.cleaning.planet import is_event_ad_hoc
from app.configuration.location_addresses import catalog, save as save_location_address
from app.configuration.store import required, valid_day
from app.importers.reference import norm
from app.shift_location import movement_key
from app.transport_defaults import MODES


def save(store, data, revision):
    run_id=data.get('run_id');movement_id=data.get('movement_id');choice=data.get('choice')
    if type(run_id) is not int or type(movement_id) is not int:
        raise ValueError('Kies een Event-ad-hocshift uit de maandverwerking.')
    if choice not in ('EXISTING','NEW'):
        raise ValueError('Kies een bestaande of nieuwe fysieke locatie.')
    reason=required(data.get('reason'))
    with store.transaction(revision) as db:
        row=db.execute('SELECT payload FROM matching_runs WHERE id=?',(run_id,)).fetchone()
        if not row:raise ValueError('De geselecteerde maandverwerking bestaat niet meer.')
        payload=json.loads(row['payload'])
        movement=next((item for item in payload['movements'] if item.get('id')==movement_id),None)
        if not movement or not any(is_event_ad_hoc(shift.get('customer')) for shift in movement.get('source_shifts',[])):
            raise ValueError('Deze shift is geen ongekoppelde Event-ad-hocshift.')
        agent=next((item for item in payload['agents'] if item['planet_id']==movement['planet_id']),None)
        if not agent or agent.get('worker_id') is None:
            raise ValueError('Koppel eerst de werknemer.')
        day=movement['day'];start=valid_day(data.get('valid_from'))
        if start>day:raise ValueError('De locatie moet uiterlijk op de shiftdatum geldig zijn.')
        known={item['key']:item for item in catalog(db)}
        target=required(data.get('location'));target_key=norm(target)
        created_route=None
        if choice=='EXISTING':
            if target_key not in known:raise ValueError('Kies een bestaande fysieke locatie uit de lijst.')
            target=known[target_key]['name']
        else:
            if target_key in known:raise ValueError('Deze fysieke locatie bestaat al. Kies bestaande locatie.')
            mode=data.get('mode')
            if mode not in MODES:raise ValueError('Kies het standaardvervoer voor de nieuwe locatie.')
            created_route=db.execute('''INSERT INTO routes(worker_id,location,location_key,mode,mode_key)
                VALUES(?,?,?,?,?)''',(agent['worker_id'],target,target_key,mode,norm(mode))).lastrowid
            store.version(db,created_route,start,None,reason,allow_missing=True)
            now=datetime.now(timezone.utc).isoformat()
            db.execute('''INSERT INTO transport_defaults
                (worker_id,location,location_key,mode,valid_from,reason,changed_at)
                VALUES(?,?,?,?,?,?,?)''',(agent['worker_id'],target,target_key,mode,start,reason,now))
            address=data.get('address')
            if not isinstance(address,dict) or not address.get('country'):
                raise ValueError('Vul het volledige locatieadres en de landcode in.')
            save_location_address(db,{'location':target,'valid_from':start,'address':address,'reason':reason})
        now=datetime.now(timezone.utc).isoformat();key=movement_key(payload,movement)
        db.execute('''INSERT INTO shift_location_choices(movement_key,location,reason,changed_at)
            VALUES(?,?,?,?)''',(key,target,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'event_location_choice','movement_key':key,
                'movement_id':movement_id,'location':target,'new_location':choice=='NEW',
                'route_id':created_route})))
        return {'location':target,'new_location':choice=='NEW','route_id':created_route}
