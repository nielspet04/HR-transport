"""Audited correction of one movement's physical location."""
from datetime import datetime,timezone
import json

from app.configuration.store import required
from app.distances import whole_kms
from app.importers.reference import norm
from app.shift_transport import movement_key
from app.transport import km_applicable
from app.transport_defaults import effective as effective_transport

SCHEMA='''
CREATE TABLE IF NOT EXISTS shift_location_choices(
 id INTEGER PRIMARY KEY, movement_key TEXT NOT NULL, location TEXT NOT NULL,
 reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS shift_location_choices_key
 ON shift_location_choices(movement_key,id);
'''


def choices(db,payload):
    latest={}
    for row in db.execute('SELECT * FROM shift_location_choices ORDER BY id'):
        latest[row['movement_key']]=dict(row)
    return {movement['id']:latest.get(movement_key(payload,movement))
        for movement in payload['movements'] if 'id' in movement}


def apply_choices(db,config,payload):
    """Apply corrections to a loaded payload; the immutable imported JSON stays intact."""
    selected=choices(db,payload)
    agents={agent['planet_id']:agent for agent in payload['agents']}
    for movement in payload['movements']:
        choice=selected.get(movement.get('id'))
        if not choice or not choice['location']:
            continue
        original=movement.get('location') or movement.get('source_location')
        location=choice['location'];day=movement['day']
        agent=agents[movement['planet_id']];worker_id=agent.get('worker_id')
        movement.update(original_location=original,location=location,location_status='MATCHED',
            location_corrected=True,location_correction_reason=choice['reason'])
        for item in payload.get('locations',[]):
            if item.get('movement_id')==movement.get('id'):
                item.update(reference_location=location,location_corrected=True)
        route_rows=[route for route in config.get('routes',[])
            if route['worker_id']==worker_id and route['location_key']==norm(location)]
        available=[]
        for route in route_rows:
            versions=[version for version in config.get('versions',[])
                if version['route_id']==route['id'] and version['valid_from']<=day]
            if not versions:
                continue
            version=max(versions,key=lambda item:(item['valid_from'],item['id']))
            applicable=km_applicable(route['mode'])
            available.append({'route_id':route['id'],'mode':route['mode'],
                'kms':str(whole_kms(version['kms'])) if applicable and version.get('kms') is not None else None,
                'km_applicable':applicable,'valid_from':version['valid_from']})
        default=effective_transport(config.get('transport_defaults',[]),worker_id,location,day) if worker_id is not None else None
        if default:
            matching=[route for route in available if norm(route['mode'])==norm(default['mode'])]
            available=matching or [{'route_id':None,'mode':default['mode'],'kms':None,
                'km_applicable':default['mode'] in ('Privé auto','Fiets'),'valid_from':default['valid_from']}]
        movement['routes']=available
        movement['route_status']='AVAILABLE' if available else 'NO_EFFECTIVE_ROUTE'
        agent_status=agent.get('status',movement.get('employee_status','MATCHED'))
        if agent_status!='MATCHED':movement['status']=agent_status
        elif not available:movement['status']='UNMATCHED_EMPLOYEE_LOCATION'
        else:movement['status']='MATCHED'
        for item in payload.get('locations',[]):
            if item.get('movement_id')==movement.get('id'):
                item['status']=movement['status']
    return payload


def save(store,data,revision):
    reset=data.get('reset') is True
    reason=required(data.get('reason'))
    with store.transaction(revision) as db:
        row=db.execute('SELECT payload FROM matching_runs WHERE id=?',(data.get('run_id'),)).fetchone()
        if not row:raise ValueError('Onbekende maandverwerking.')
        payload=json.loads(row['payload'])
        movement=next((item for item in payload['movements'] if item.get('id')==data.get('movement_id')),None)
        if not movement:raise ValueError('Onbekende shift.')
        agent=next(item for item in payload['agents'] if item['planet_id']==movement['planet_id'])
        if agent.get('worker_id') is None:raise ValueError('Koppel eerst de werknemer.')
        location=''
        if not reset:
            location=required(data.get('location'))
            from app.configuration.location_addresses import catalog
            canonical=next((item['name'] for item in catalog(db) if item['key']==norm(location)),None)
            if canonical is None:raise ValueError('Kies een bestaande fysieke locatie.')
            location=canonical
        now=datetime.now(timezone.utc).isoformat();key=movement_key(payload,movement)
        db.execute('INSERT INTO shift_location_choices(movement_key,location,reason,changed_at) VALUES(?,?,?,?)',
            (key,location,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'shift_location_choice','movement_key':key,
                'location':location or None,'reset':reset})))
