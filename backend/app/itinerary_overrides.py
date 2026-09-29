"""Audited HR override for one gap between two same-day movements."""
from datetime import datetime,timezone
import json

from app.configuration.store import required
from app.shift_transport import movement_key

SCHEMA='''
CREATE TABLE IF NOT EXISTS itinerary_transfer_overrides(
 id INTEGER PRIMARY KEY, movement_key TEXT NOT NULL, direct_transfer INTEGER NOT NULL,
 reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS itinerary_transfer_overrides_key
 ON itinerary_transfer_overrides(movement_key,id);
CREATE TABLE IF NOT EXISTS itinerary_employee_defaults(
 id INTEGER PRIMARY KEY, worker_id INTEGER NOT NULL REFERENCES workers(id),
 direct_transfer INTEGER NOT NULL, reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS itinerary_employee_defaults_worker
 ON itinerary_employee_defaults(worker_id,id);
'''


def overrides(db,payload):
    latest={}
    for row in db.execute('SELECT * FROM itinerary_transfer_overrides ORDER BY id'):
        latest[row['movement_key']]=dict(row)
    return {movement['id']:latest.get(movement_key(payload,movement))
        for movement in payload['movements'] if 'id' in movement}


def employee_defaults(db):
    latest={}
    for row in db.execute('SELECT * FROM itinerary_employee_defaults ORDER BY id'):
        latest[row['worker_id']]=dict(row)
    return latest


def direct_choices(db,payload):
    movement_choices=overrides(db,payload);employee_choices=employee_defaults(db)
    agents={agent['planet_id']:agent for agent in payload['agents']};result={}
    for movement in payload['movements']:
        movement_id=movement.get('id')
        if movement_id is None:
            continue
        worker_id=agents[movement['planet_id']].get('worker_id')
        default=employee_choices.get(worker_id)
        employee_default_active=bool(default and default['direct_transfer'])
        specific=movement_choices.get(movement_id)
        if specific:
            result[movement_id]={'direct_transfer':bool(specific['direct_transfer']),'scope':'DAY',
                'employee_default_active':employee_default_active}
            continue
        if default:
            result[movement_id]={'direct_transfer':bool(default['direct_transfer']),'scope':'EMPLOYEE',
                'employee_default_active':employee_default_active}
    return result


def ensure_confirmed_defaults(db):
    """Persist the HR-confirmed recurring exception once, without re-enabling it after opt-out."""
    workers=db.execute("SELECT id FROM workers WHERE name_key IN ('kurt yasin','yasin kurt') ORDER BY id").fetchall()
    now=datetime.now(timezone.utc).isoformat();created=0
    for worker in workers:
        if db.execute('SELECT 1 FROM itinerary_employee_defaults WHERE worker_id=?',(worker['id'],)).fetchone():
            continue
        reason='HR bevestigt: Yasin Kurt rijdt bij meerdere shiften rechtstreeks door, ook bij meer dan twee uur pauze'
        db.execute('''INSERT INTO itinerary_employee_defaults
            (worker_id,direct_transfer,reason,changed_at) VALUES(?,?,?,?)''',(worker['id'],1,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'itinerary_employee_default','worker_id':worker['id'],'direct_transfer':True})))
        created+=1
    return created


def _context(db,data):
    row=db.execute('SELECT payload FROM matching_runs WHERE id=?',(data.get('run_id'),)).fetchone()
    if not row:raise ValueError('Onbekende maandverwerking.')
    payload=json.loads(row['payload'])
    movement=next((item for item in payload['movements'] if item.get('id')==data.get('movement_id')),None)
    if not movement:raise ValueError('Onbekende shiftbeweging.')
    from app.shift_transport import choices
    transport=choices(db,payload)
    excluded={movement_id for movement_id,choice in transport.items()
        if choice and choice['mode']=='TELEWORK'}
    from app.itinerary import itineraries
    leg=itineraries(payload,excluded).get((movement['planet_id'],movement['day'],movement['id']))
    if not leg or leg.get('error') or leg.get('sequence',0)<2 or leg.get('gap_minutes') is None:
        raise ValueError('Deze shift heeft geen zekere voorgaande shift om rechtstreeks te koppelen.')
    return payload,movement,leg


def save(store,data,revision):
    direct=data.get('direct_transfer')
    if type(direct) is not bool:
        raise ValueError('Bevestig of de agent rechtstreeks naar de volgende shift ging.')
    reason=required(data.get('reason'))
    with store.transaction(revision) as db:
        payload,movement,leg=_context(db,data)
        if direct and leg['gap_minutes']<=120:
            raise ValueError('Deze shiften zijn door de gewone twee-uursregel al rechtstreeks gekoppeld.')
        key=movement_key(payload,movement);now=datetime.now(timezone.utc).isoformat()
        db.execute('''INSERT INTO itinerary_transfer_overrides
            (movement_key,direct_transfer,reason,changed_at) VALUES(?,?,?,?)''',
            (key,int(direct),reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'itinerary_transfer_override',
                'movement_key':key,'direct_transfer':direct})))


def save_employee_default(store,data,revision):
    direct=data.get('direct_transfer')
    if type(direct) is not bool:
        raise ValueError('Bevestig de standaard voor rechtstreekse ritten.')
    reason=required(data.get('reason'))
    with store.transaction(revision) as db:
        payload,movement,leg=_context(db,data)
        if direct and leg['gap_minutes']<=120:
            raise ValueError('Kies een voorbeeld met meer dan twee uur pauze voor deze werknemersstandaard.')
        agent=next(item for item in payload['agents'] if item['planet_id']==movement['planet_id'])
        worker_id=agent.get('worker_id')
        if type(worker_id) is not int:
            raise ValueError('Koppel eerst de werknemer.')
        now=datetime.now(timezone.utc).isoformat()
        db.execute('''INSERT INTO itinerary_employee_defaults
            (worker_id,direct_transfer,reason,changed_at) VALUES(?,?,?,?)''',
            (worker_id,int(direct),reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
            (now,reason,json.dumps({'action':'itinerary_employee_default',
                'worker_id':worker_id,'direct_transfer':direct})))
