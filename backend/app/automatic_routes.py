"""Automatic address/route provisioning, with durable intent before every API call."""
from datetime import datetime,timezone,date
import json
import threading
from app import geocoding,routing

SCHEMA='''CREATE TABLE IF NOT EXISTS automatic_route_settings(
 id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,status TEXT NOT NULL,
 report TEXT NOT NULL);
INSERT OR IGNORE INTO automatic_route_settings VALUES(1,0,'IDLE','{}');'''
_workers={}
_lock=threading.Lock()


def state(db):
    row=dict(db.execute('SELECT * FROM automatic_route_settings WHERE id=1').fetchone())
    row['enabled']=bool(row['enabled']);row['report']=json.loads(row['report']);return row


def enabled(store):
    with store.connect() as db:return bool(db.execute('SELECT enabled FROM automatic_route_settings').fetchone()[0])


def report(store,status,details):
    with store.connect() as db:
        db.execute('UPDATE automatic_route_settings SET status=?,report=? WHERE id=1',(status,json.dumps(details)));db.commit()


def run(store):
    counts={'geocoded':0,'routes':0,'errors':0}
    if not enabled(store):return counts
    if not geocoding.configured():report(store,'BLOCKED',{'message':'Mapbox-token ontbreekt.'});return counts
    report(store,'RUNNING',counts)
    with store.connect() as db:
        addresses=[json.loads(r['address']) for table in ('worker_addresses','location_address_versions') for r in db.execute(f'SELECT address FROM {table} WHERE valid_from<=?',(date.today().isoformat(),))]
    for address in addresses:
        if not enabled(store):break
        if address.get('country')!='BE':continue
        digest=geocoding.fingerprint(address);now=datetime.now(timezone.utc).isoformat()
        with store.connect() as db:
            if db.execute('SELECT 1 FROM address_geocodes WHERE address_hash=?',(digest,)).fetchone():continue
        with store.transaction() as db:
            if db.execute('SELECT 1 FROM address_geocodes WHERE address_hash=?',(digest,)).fetchone():continue
            db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at,reason) VALUES(?,?,?,?,?,?)',
                (digest,'mapbox-v6-permanent','PENDING','{}',now,'Automatische aanvraag; intentie vóór API opgeslagen'))
        try:
            result=geocoding.request_address(address)
            status=result['status']
            if status=='REVIEW':
                if result.get('eligible') is True:status='CONFIRMED'
                else:result['automatic_review_required']=True
        except ValueError as error:result={'message':str(error)};status='ERROR'
        with store.transaction() as db:
            db.execute('UPDATE address_geocodes SET status=?,result=?,reviewed_at=?,reason=? WHERE address_hash=?',
                (status,json.dumps(result),now if status=='CONFIRMED' else None,'Automatisch: alleen exacte/hoge adresmatch bevestigd',digest))
            db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(now,'Automatische geocodering',json.dumps({'address_hash':digest,'status':status})))
        counts['geocoded']+=1;counts['errors']+=status in ('ERROR','NO_MATCH','REVIEW');report(store,'RUNNING',counts)
    with store.connect() as db:latest=db.execute('SELECT id FROM matching_runs WHERE month NOT IN (SELECT month FROM excluded_months) ORDER BY id DESC LIMIT 1').fetchone()
    if latest and enabled(store):
        # Refresh identities/modes after additions; this never calls Mapbox itself.
        with store.connect() as db:
            from app.matching import configuration_digest
            payload=json.loads(db.execute('SELECT payload FROM matching_runs WHERE id=?',(latest['id'],)).fetchone()[0])
            stale=payload['configuration_digest']!=configuration_digest(store.matching_config(db))
        if stale:
            with store.connect() as db:revision=db.execute('SELECT revision FROM meta').fetchone()[0]
            store._apply('matching_refresh',{'run_id':latest['id']},revision)
            with store.connect() as db:latest=db.execute('SELECT id FROM matching_runs WHERE month NOT IN (SELECT month FROM excluded_months) ORDER BY id DESC LIMIT 1').fetchone()
        prepared=store.get_route_plan(latest['id'])
        for item in prepared['routes']:
            if not enabled(store):break
            if item['cached']:continue
            with store.connect() as db:revision=db.execute('SELECT revision FROM meta').fetchone()[0]
            routing.request_one(store,{'run_id':latest['id'],'cache_key':item['cache_key'],'consent':True},revision)
            counts['routes']+=1
            with store.connect() as db:status=db.execute('SELECT status FROM route_distances WHERE cache_key=?',(item['cache_key'],)).fetchone()[0]
            counts['errors']+=status!='READY';report(store,'RUNNING',counts)
        counts['blocked_movements']=len(prepared['blocked'])
    with store.connect() as db:
        counts['attention_results']=sum(r['status'] in ('PENDING','ERROR','NO_MATCH') or r['status']=='REVIEW' and json.loads(r['result']).get('automatic_review_required',False) for r in db.execute('SELECT status,result FROM address_geocodes'))+db.execute("SELECT count(*) FROM route_distances WHERE status IN ('PENDING','ERROR')").fetchone()[0]
    report(store,'DONE' if enabled(store) else 'STOPPED',counts);return counts


def trigger(store):
    if not enabled(store):return
    key=str(store.path.resolve())
    with _lock:
        if key in _workers:
            _workers[key].set();return
        event=threading.Event();_workers[key]=event
    def work():
        try:
            while True:
                event.clear()
                try:run(store)
                except Exception:report(store,'ERROR',{'message':'Automatische verwerking onderbroken. Bestaande resultaten blijven bewaard; vernieuw de verwerking. Geen automatische herhaling van API-intenties.'})
                with _lock:
                    if not event.is_set():_workers.pop(key,None);break
        finally:
            with _lock:
                if _workers.get(key) is event:_workers.pop(key,None)
    report(store,'QUEUED',{'message':'Automatische verwerking ingepland.'})
    threading.Thread(target=work,daemon=True,name='hr-automatic-routes').start()
