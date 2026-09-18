"""Persist default car transport only for confirmed, previously unconfigured pairs."""
from datetime import datetime,timezone
import json
from app.importers.reference import norm


def seed(store,db,payloads):
    existing={(r['worker_id'],r['location_key']) for r in db.execute('SELECT worker_id,location_key FROM routes')}
    needed={}
    for payload in payloads:
        agents={a['planet_id']:a for a in payload['agents']}
        for movement in payload['movements']:
            agent=agents[movement['planet_id']]
            if agent['status']!='MATCHED' or movement['location_status']!='MATCHED':continue
            wid=agent['worker_id'];location=movement['location'];key=(wid,norm(location))
            if key in existing:continue
            previous=needed.get(key)
            if not previous or movement['day']<previous[1]:needed[key]=(location,movement['day'])
    for (wid,loc_key),(location,day) in sorted(needed.items()):
        rid=db.execute('INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,?,?,?,?)',
            (wid,location,loc_key,'Privé auto','privé auto')).lastrowid
        reason='Automatische standaard privéauto voor nieuwe werknemer–locatiecombinatie'
        store.version(db,rid,day,None,reason,allow_missing=True)
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (datetime.now(timezone.utc).isoformat(),reason,json.dumps({'worker_id':wid,'route_id':rid,'valid_from':day})))
    return len(needed)
