"""Persist default car transport only for confirmed, previously unconfigured pairs."""
from datetime import datetime,timezone
import json
from app.importers.reference import norm


def seed(store,db,payloads):
    route_groups={}
    for row in db.execute('SELECT worker_id,location,location_key,mode FROM routes ORDER BY id'):
        route_groups.setdefault((row['worker_id'],row['location_key']),[]).append(dict(row))
    existing=set(route_groups)
    configured={(r['worker_id'],r['location_key']) for r in db.execute(
        'SELECT DISTINCT worker_id,location_key FROM transport_defaults')}
    needed={};backfill={}
    for payload in payloads:
        agents={a['planet_id']:a for a in payload['agents']}
        for movement in payload['movements']:
            agent=agents[movement['planet_id']]
            if agent['status']!='MATCHED' or movement['location_status']!='MATCHED':continue
            wid=agent['worker_id'];location=movement['location'];key=(wid,norm(location))
            # A monthly export establishes the default for the whole export
            # month, not from the upload date or the first retained shift.
            month_start=movement['day'][:7]+'-01'
            if key in existing:
                # Older profiles may predate transport_defaults. If exactly
                # one stored route identifies the mode unambiguously, make it
                # effective for the export month so cached Mapbox distance can
                # be used without inventing a historical manual distance.
                modes={norm(row['mode']):row['mode'] for row in route_groups[key]}
                if key not in configured and len(modes)==1:
                    previous=backfill.get(key)
                    if not previous or month_start<previous[2]:
                        backfill[key]=(location,next(iter(modes.values())),month_start)
                continue
            previous=needed.get(key)
            if not previous or month_start<previous[1]:needed[key]=(location,month_start)
    for (wid,loc_key),(location,day) in sorted(needed.items()):
        rid=db.execute('INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,?,?,?,?)',
            (wid,location,loc_key,'Privé auto','privé auto')).lastrowid
        reason='Automatische standaard privéauto voor nieuwe werknemer–locatiecombinatie'
        store.version(db,rid,day,None,reason,allow_missing=True)
        db.execute('INSERT INTO transport_defaults(worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)',
            (wid,location,loc_key,'Privé auto',day,reason,datetime.now(timezone.utc).isoformat()))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (datetime.now(timezone.utc).isoformat(),reason,json.dumps({'worker_id':wid,'route_id':rid,'valid_from':day})))
    for (wid,loc_key),(location,mode,day) in sorted(backfill.items()):
        reason='Automatische vervoerswijze vanaf exportmaand op basis van de enige bestaande route'
        now=datetime.now(timezone.utc).isoformat()
        db.execute('''INSERT INTO transport_defaults
            (worker_id,location,location_key,mode,valid_from,reason,changed_at)
            VALUES(?,?,?,?,?,?,?)''',(wid,location,loc_key,mode,day,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'worker_id':wid,'location':location,'mode':mode,'valid_from':day})))
    return len(needed)+len(backfill)
