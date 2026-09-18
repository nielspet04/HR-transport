"""Append-only, employee-specific corrections of cached provider distances."""
from datetime import datetime,timezone
import json
from app.distances import display_route
from app.geocoding import fingerprint

SCHEMA='''CREATE TABLE IF NOT EXISTS route_distance_corrections(
 id INTEGER PRIMARY KEY, route_id INTEGER NOT NULL REFERENCES route_distances(id),
 worker_id INTEGER NOT NULL REFERENCES workers(id), kms INTEGER,
 reason TEXT NOT NULL, changed_at TEXT NOT NULL);'''


def cached_distances(db):
    rows=[display_route(r) for r in db.execute('SELECT * FROM route_distances ORDER BY id')]
    history={};active={}
    for row in db.execute('SELECT * FROM route_distance_corrections ORDER BY id'):
        c=dict(row);history.setdefault(c['route_id'],[]).append(c);active[(c['route_id'],c['worker_id'])]=c
    for r in rows:
        corrections=[dict(c) for c in db.execute('SELECT * FROM location_transfer_corrections WHERE route_id=? ORDER BY id',(r['id'],))]
        r['transfer_correction_history']=corrections
        r['transfer_override']=corrections[-1] if corrections and corrections[-1]['kms'] is not None else None
        r['correction_history']=history.get(r['id'],[])
        r['overrides']=[c for (rid,wid),c in active.items() if rid==r['id'] and c['kms'] is not None]
    return rows


def effective_distance(row, worker_id):
    result=dict(row)
    correction=next((c for c in result.get('overrides',[]) if c['worker_id']==worker_id),None)
    result['mapbox_kms']=result.get('kms')
    result['distance_source']='HR' if correction else 'Mapbox'
    shared=result.get('transfer_override')
    if shared:result.update(kms=str(shared['kms']),override_reason=shared['reason'],distance_source='HR')
    if correction:result.update(kms=str(correction['kms']),override_reason=correction['reason'])
    if correction:result['distance_source']='HR'
    return result


def apply(store,data,revision):
    reason=data.get('reason')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise ValueError('Vul een reden in (maximaal 500 tekens).')
    value=data.get('kms')
    if data.get('reset') is True:value=None
    else:
        if isinstance(value,str) and value.isascii() and value.isdigit():value=int(value)
        if type(value) is not int or not 0<=value<=100000:raise ValueError('Vul gehele kilometers tussen 0 en 100000 in.')
    if type(data.get('worker_id')) is not int or type(data.get('route_id')) is not int:raise ValueError('Ongeldige werknemer of route.')
    with store.transaction(revision) as db:
        route=db.execute('SELECT * FROM route_distances WHERE id=? AND status=?',(data['route_id'],'READY')).fetchone()
        if not route:raise ValueError('Geen opgeslagen Mapbox-afstand beschikbaar.')
        addresses=db.execute('SELECT address FROM worker_addresses WHERE worker_id=?',(data['worker_id'],))
        owned=any(fingerprint(json.loads(a['address']))==route['origin_hash'] for a in addresses)
        saved=db.execute('SELECT contexts FROM route_saved_contexts WHERE route_id=?',(route['id'],)).fetchone()
        if saved:owned=owned or any(c['worker_id']==data['worker_id'] for c in json.loads(saved['contexts']))
        if not owned:
            from app.routing import plan
            latest=db.execute('SELECT id FROM matching_runs ORDER BY id DESC LIMIT 1').fetchone()
            current=plan(db,store.matching_config(db),latest['id']) if latest else {'routes':[]}
            owned=any(r['cache_key']==route['cache_key'] and any(c['worker_id']==data['worker_id'] for c in r['contexts']) for r in current['routes'])
        if not owned:raise ValueError('Deze route hoort niet bij deze werknemer.')
        now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO route_distance_corrections(route_id,worker_id,kms,reason,changed_at) VALUES(?,?,?,?,?)',
                   (route['id'],data['worker_id'],value,reason.strip(),now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                   (now,reason.strip(),json.dumps({'action':'route_distance_override','route_id':route['id'],'worker_id':data['worker_id'],'kms':value})))
