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


def save(store,data,revision):
    mode=data.get('mode');start=valid_day(data.get('valid_from'));reason=required(data.get('reason'));wid=data.get('worker_id');location=required(data.get('location'))
    if mode not in MODES:raise ValueError('Kies privéauto, fiets, trein, dienstwagen of mobiliteitsbudget.')
    with store.transaction(revision) as db:
        if type(wid) is not int or not db.execute('SELECT 1 FROM workers WHERE id=?',(wid,)).fetchone():raise ValueError('Onbekende werknemer.')
        now=datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO transport_defaults(worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)',(wid,location,norm(location),mode,start,reason,now))
        db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(now,reason,json.dumps({'action':'transport_default','worker_id':wid,'location':location,'mode':mode,'valid_from':start})))
