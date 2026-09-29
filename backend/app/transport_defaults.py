"""Effective-dated default transport per worker and physical location."""
from datetime import datetime,timezone
import json
from app.importers.reference import norm
from app.configuration.store import required,valid_day

SCHEMA='''
CREATE TABLE IF NOT EXISTS transport_defaults(
 id INTEGER PRIMARY KEY, worker_id INTEGER NOT NULL REFERENCES workers(id),
 location TEXT NOT NULL, location_key TEXT NOT NULL, mode TEXT NOT NULL,
 valid_from TEXT NOT NULL, reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS transport_defaults_lookup ON transport_defaults(worker_id,location_key,valid_from,id);
'''
MODES=('Privé auto','Fiets','Trein','Dienstwagen','Mob budget')


def effective(rows,worker_id,location,day):
    eligible=[r for r in rows if r['worker_id']==worker_id and r['location_key']==norm(location) and r['valid_from']<=day]
    return max(eligible,key=lambda r:(r['valid_from'],r['id'])) if eligible else None


def apply_to_payload(config,payload):
    """Refresh immutable import movements with the currently effective default.

    Matching runs retain the original evidence, but a later HR transport change
    must immediately govern calculation and route planning. A full source
    re-import remains necessary to clear the configuration-stale audit flag.
    """
    from app.distances import whole_kms
    from app.transport import km_applicable

    agents={agent['planet_id']:agent for agent in payload.get('agents',[])}
    for movement in payload.get('movements',[]):
        agent=agents.get(movement.get('planet_id'),{})
        worker_id=agent.get('worker_id')
        location=movement.get('location')
        day=movement.get('day')
        if worker_id is None or not location or not day:
            continue
        default=effective(config.get('transport_defaults',[]),worker_id,location,day)
        if not default:
            continue
        routes=[]
        for route in config.get('routes',[]):
            if route['worker_id']!=worker_id or route['location_key']!=norm(location) or norm(route['mode'])!=norm(default['mode']):
                continue
            versions=[version for version in config.get('versions',[])
                if version['route_id']==route['id'] and version['valid_from']<=day]
            if not versions:
                continue
            version=max(versions,key=lambda item:(item['valid_from'],item['id']))
            applicable=km_applicable(route['mode'])
            routes.append({'route_id':route['id'],'mode':route['mode'],
                'kms':str(whole_kms(version['kms'])) if applicable and version.get('kms') is not None else None,
                'km_applicable':applicable,'valid_from':version['valid_from']})
        movement['routes']=routes or [{'route_id':None,'mode':default['mode'],'kms':None,
            'km_applicable':km_applicable(default['mode']),'valid_from':default['valid_from']}]
        movement['route_status']='AVAILABLE'
    return payload


def save(store,data,revision):
    mode=data.get('mode');start=valid_day(data.get('valid_from'));reason=required(data.get('reason'));wid=data.get('worker_id');location=required(data.get('location'))
    if mode not in MODES:raise ValueError('Kies privéauto, fiets, trein, dienstwagen of mobiliteitsbudget.')
    with store.transaction(revision) as db:
        if type(wid) is not int or not db.execute('SELECT 1 FROM workers WHERE id=?',(wid,)).fetchone():raise ValueError('Onbekende werknemer.')
        now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO transport_defaults(worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)',(wid,location,norm(location),mode,start,reason,now))
        route=db.execute('''SELECT id FROM routes WHERE worker_id=? AND location_key=? AND mode_key=?''',
            (wid,norm(location),norm(mode))).fetchone()
        if not route:
            route_id=db.execute('''INSERT INTO routes(worker_id,location,location_key,mode,mode_key)
                VALUES(?,?,?,?,?)''',(wid,location,norm(location),mode,norm(mode))).lastrowid
            store.version(db,route_id,start,None,reason,allow_missing=True)
        elif not db.execute('SELECT 1 FROM versions WHERE route_id=? AND valid_from<=?',
                (route['id'],start)).fetchone():
            # The transport choice and its route must become effective together.
            # Add a historical availability marker without changing the later
            # distance version; cached Mapbox/HR distance remains authoritative.
            store.version(db,route['id'],start,None,reason,
                allow_missing=True,allow_historical=True)
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(now,reason,json.dumps({'action':'transport_default','worker_id':wid,'location':location,'mode':mode,'valid_from':start})))
