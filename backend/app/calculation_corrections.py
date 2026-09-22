"""Append-only HR corrections to an otherwise calculated shift amount."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import json
from app.shift_transport import movement_key
from app.configuration.store import required

SCHEMA='''CREATE TABLE IF NOT EXISTS calculation_amount_corrections(
 id INTEGER PRIMARY KEY, movement_key TEXT NOT NULL, amount TEXT,
 reason TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS calculation_amount_corrections_key ON calculation_amount_corrections(movement_key,id);'''


def corrections(db,payload):
    history={};latest={}
    for row in db.execute('SELECT * FROM calculation_amount_corrections ORDER BY id'):
        item=dict(row);history.setdefault(item['movement_key'],[]).append(item);latest[item['movement_key']]=item
    result={}
    for movement in payload['movements']:
        key=movement_key(payload,movement);active=latest.get(key)
        result[movement['id']]={'history':history.get(key,[]),'active':active if active and active['amount'] is not None else None}
    return result


def save(store,data,revision):
    reason=required(data.get('reason'));value=None if data.get('reset') is True else data.get('amount')
    if value is not None:
        try:amount=Decimal(str(value).replace(',','.'))
        except (InvalidOperation,ValueError):raise ValueError('Vul een geldig bedrag in.') from None
        if not amount.is_finite() or amount<0 or amount>100000 or amount!=amount.quantize(Decimal('.01')):raise ValueError('Bedrag moet tussen €0 en €100.000 liggen, met maximaal twee decimalen.')
        value=format(amount,'.2f')
    with store.transaction(revision) as db:
        row=db.execute('SELECT payload FROM matching_runs WHERE id=?',(data.get('run_id'),)).fetchone()
        if not row:raise ValueError('Onbekende maandverwerking.')
        payload=json.loads(row['payload']);movement=next((m for m in payload['movements'] if m['id']==data.get('movement_id')),None)
        if not movement:raise ValueError('Onbekende shiftbeweging.')
        now=datetime.now(timezone.utc).isoformat();key=movement_key(payload,movement)
        db.execute('INSERT INTO calculation_amount_corrections(movement_key,amount,reason,changed_at) VALUES(?,?,?,?)',(key,value,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(now,reason,json.dumps({'action':'calculation_amount_correction','movement_key':key,'amount':value})))
