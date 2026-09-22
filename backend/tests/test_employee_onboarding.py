import json
import pytest

from app.configuration.routes import RouteStore


def prepared(tmp_path,monkeypatch):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Bestaand Profiel','location':'LUCHTHAVEN','mode':'Privé auto',
        'kms':'10','valid_from':'2026-01-01','reason':'Testlocatie'},store.snapshot()['revision'])
    payload={'month':'2026-08','created_at':'2026-09-01T00:00:00+00:00','source_sha256':'source-hash',
        'configuration_digest':'old','agents':[{'planet_id':'5009','source_names':['Peters Niels'],
            'source_keys':['peters niels'],'worker_id':None,'worker_name':None,
            'status':'UNMATCHED_EMPLOYEE','method':'NORMALIZED_NAME','suggestions':[]}],
        'locations':[],'summary':{},'source_manifest':[{'row':2,'planet_id':'5009'}],
        'movements':[{'id':1,'planet_id':'5009','day':'2026-08-31','source_location':'LUCHTHAVEN',
            'location':'LUCHTHAVEN','employee_status':'UNMATCHED_EMPLOYEE','location_status':'MATCHED',
            'status':'UNMATCHED_EMPLOYEE','routes':[],'source_shifts':[{'row':2,'customer':'ICTS EUROPE CYBERSECURITY'}]}]}
    with store.transaction() as db:
        db.execute('INSERT INTO external_reference_imports VALUES(?,?,?)',('refs','2026-01-01','{}'))
        db.execute('''INSERT INTO external_reference_candidates
            (import_hash,source_row,name,external_reference,status,worker_id) VALUES(?,?,?,?,?,?)''',
            ('refs',8,'Peters Niels','05182410005024001','REVIEW',None))
        run=db.execute('INSERT INTO matching_runs(month,created_at,source_path,payload) VALUES(?,?,?,?)',
            ('2026-08','2026-09-01T00:00:00+00:00','unused.xlsx',json.dumps(payload))).lastrowid
    monkeypatch.setattr(store,'process_matching_file',lambda db,source,expected_hash=None:[{'month':'2026-08'}])
    return store,run


def data(run):
    return {'run_id':run,'planet_id':'5009','name':'Peters Niels','valid_from':'2026-08-31',
        'external_reference':'05182410005024001','reason':'Nieuwe werknemer bevestigd',
        'address':{'street':'Teststraat','number':'12','unit':'','postal_code':'1000','city':'Brussel','country':'BE'},
        'assignments':[{'source_location':'LUCHTHAVEN','location':'LUCHTHAVEN','mode':'Privé auto'}]}


def test_onboarding_saves_complete_profile_atomically(tmp_path,monkeypatch):
    store,run=prepared(tmp_path,monkeypatch)
    result=store.apply('employee_onboard',data(run),store.snapshot()['revision'])
    assert result['name']=='Peters Niels' and result['routes']==1
    state=store.snapshot();worker=next(w for w in state['workers'] if w['name']=='Peters Niels')
    assert next(a for a in state['addresses'] if a['worker_id']==worker['id'])['address']['city']=='Brussel'
    assert next(r for r in state['external_references'] if r['worker_id']==worker['id'])['external_reference']=='05182410005024001'
    assert next(c for c in state['external_reference_candidates'] if c['name']=='Peters Niels')['status']=='LINKED'
    route=next(r for r in state['routes'] if r['worker_id']==worker['id'])
    assert route['location']=='LUCHTHAVEN' and route['mode']=='Privé auto'
    assert next(t for t in state['transport_defaults'] if t['worker_id']==worker['id'])['valid_from']=='2026-08-31'
    assert next(link for link in state['employee_links'] if link['planet_id']=='5009')['worker_id']==worker['id']


def test_onboarding_failure_rolls_back_everything(tmp_path,monkeypatch):
    store,run=prepared(tmp_path,monkeypatch);before=store.snapshot()
    invalid=data(run);invalid['address']={**invalid['address'],'country':''}
    with pytest.raises(ValueError,match='volledige woonadres'):
        store.apply('employee_onboard',invalid,before['revision'])
    after=store.snapshot()
    assert len(after['workers'])==len(before['workers'])
    assert not any(link['planet_id']=='5009' for link in after['employee_links'])
    assert next(c for c in after['external_reference_candidates'] if c['name']=='Peters Niels')['status']=='REVIEW'


def test_onboarding_rejects_existing_worker_or_incomplete_locations(tmp_path,monkeypatch):
    store,run=prepared(tmp_path,monkeypatch)
    existing=data(run);existing['name']='Bestaand Profiel'
    with pytest.raises(ValueError,match='bestaat al'):
        store.apply('employee_onboard',existing,store.snapshot()['revision'])
    missing=data(run);missing['assignments']=[]
    with pytest.raises(ValueError,match='werklocatie'):
        store.apply('employee_onboard',missing,store.snapshot()['revision'])
