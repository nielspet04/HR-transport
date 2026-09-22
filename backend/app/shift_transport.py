"""Audited transport choice for one retained Planet movement."""
from datetime import datetime,timezone
from hashlib import sha256
import json

SCHEMA='''
CREATE TABLE IF NOT EXISTS shift_transport_choices(
 id INTEGER PRIMARY KEY, movement_key TEXT NOT NULL, mode TEXT NOT NULL,
 reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS shift_transport_choices_key ON shift_transport_choices(movement_key,id);
CREATE TABLE IF NOT EXISTS bicycle_tariffs(
 id INTEGER PRIMARY KEY, valid_from TEXT NOT NULL, rate_per_km TEXT NOT NULL,
 source TEXT NOT NULL, reason TEXT NOT NULL, changed_at TEXT NOT NULL);
'''
MODES=('DEFAULT','AUTO','BIKE','TRAIN')


def movement_key(payload,movement):
    rows=sorted(s['row'] for s in movement.get('source_shifts',[]))
    raw=[payload['source_sha256'],payload['month'],movement['planet_id'],movement['day'],rows]
    return sha256(json.dumps(raw,separators=(',',':')).encode()).hexdigest()


def choices(db,payload):
    latest={}
    for row in db.execute('SELECT * FROM shift_transport_choices ORDER BY id'):
        latest[row['movement_key']]=dict(row)
    return {m['id']:latest.get(movement_key(payload,m)) for m in payload['movements'] if 'id' in m}


def save(store,data,revision):
    mode=data.get('mode');reason=data.get('reason')
    if mode not in MODES:raise ValueError('Kies standaard, auto, fiets of trein.')
    from app.configuration.store import required
    reason=required(reason)
    with store.transaction(revision) as db:
        row=db.execute('SELECT payload FROM matching_runs WHERE id=?',(data.get('run_id'),)).fetchone()
        if not row:raise ValueError('Onbekende maandverwerking.')
        payload=json.loads(row['payload'])
        movement=next((m for m in payload['movements'] if m['id']==data.get('movement_id')),None)
        if not movement:raise ValueError('Onbekende shiftbeweging.')
        agent=next(a for a in payload['agents'] if a['planet_id']==movement['planet_id'])
        if agent.get('worker_id') is None or movement.get('location_status',movement.get('status'))!='MATCHED':
            raise ValueError('Koppel eerst werknemer en locatie.')
        key=movement_key(payload,movement);now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO shift_transport_choices(movement_key,mode,reason,changed_at) VALUES(?,?,?,?)',(key,mode,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'shift_transport_choice','movement_key':key,'mode':mode})))


def snapshot(db):
    return {'shift_transport_choices':[dict(r) for r in db.execute('SELECT * FROM shift_transport_choices ORDER BY id')],
            'bicycle_tariffs':[dict(r) for r in db.execute('SELECT * FROM bicycle_tariffs ORDER BY id')]}
