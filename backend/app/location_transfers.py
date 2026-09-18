"""Physical location-to-location distance overview and shared HR corrections."""
import json
from datetime import datetime,timezone

SCHEMA='''CREATE TABLE IF NOT EXISTS location_transfer_corrections(
 id INTEGER PRIMARY KEY,route_id INTEGER NOT NULL REFERENCES route_distances(id),
 kms INTEGER,reason TEXT NOT NULL,changed_at TEXT NOT NULL);'''


def overview(db,config):
    from app.route_corrections import cached_distances
    cached={r['id']:r for r in cached_distances(db)};items={}
    def add(key,contexts,saved):
        transfers=[c for c in contexts if c.get('origin_location')]
        if not transfers:return
        item=items.setdefault(key,{'cache_key':key,'contexts':[],'cached':saved})
        for c in transfers:
            if c not in item['contexts']:item['contexts'].append(c)
    for row in db.execute('SELECT * FROM route_saved_contexts'):
        saved=cached.get(row['route_id'])
        if saved:add(saved['cache_key'],json.loads(row['contexts']),saved)
    latest=db.execute('SELECT id FROM matching_runs ORDER BY id DESC LIMIT 1').fetchone()
    if latest:
        from app.routing import plan
        try:
            for r in plan(db,config,latest['id'])['routes']:add(r['cache_key'],r['contexts'],r['cached'])
        except ValueError:pass
    return list(items.values())


def correct(store,data,revision):
    # Same validation contract, but a physical pair correction applies to every worker.
    reason=data.get('reason');value=data.get('kms')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise ValueError('Vul een reden in (maximaal 500 tekens).')
    if data.get('reset') is True:value=None
    else:
        if isinstance(value,str) and value.isascii() and value.isdigit():value=int(value)
        if type(value) is not int or not 0<=value<=100000:raise ValueError('Vul gehele kilometers tussen 0 en 100000 in.')
    if type(data.get('route_id')) is not int:raise ValueError('Ongeldige route.')
    with store.transaction(revision) as db:
        items=overview(db,store.matching_config(db))
        item=next((r for r in items if r['cached'] and r['cached']['id']==data['route_id'] and r['cached']['status']=='READY'),None)
        if not item:raise ValueError('Geen opgeslagen tussenlocatieroute beschikbaar.')
        now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO location_transfer_corrections(route_id,kms,reason,changed_at) VALUES(?,?,?,?)',(data['route_id'],value,reason.strip(),now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(now,reason.strip(),json.dumps({'action':'location_transfer_override','route_id':data['route_id'],'kms':value})))
