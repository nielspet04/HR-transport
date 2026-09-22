import json
import pytest

from app.configuration.routes import RouteStore


def prepared(tmp_path,monkeypatch):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Voorbeeld Alex','location':'LUCHTHAVEN','mode':'Privé auto',
        'kms':'10','valid_from':'2026-01-01','reason':'Test'},store.snapshot()['revision'])
    worker=store.snapshot()['workers'][0]['id']
    payload={'month':'2026-08','created_at':'2026-09-01T00:00:00+00:00','source_sha256':'source-hash',
        'configuration_digest':'old','agents':[{'planet_id':'100','source_names':['Voorbeeld Alex'],
            'source_keys':['voorbeeld alex'],'worker_id':worker,'worker_name':'Voorbeeld Alex',
            'status':'MATCHED','method':'NORMALIZED_NAME','suggestions':[]}],
        'locations':[{'customer':'NIEUWE KLANT','physical_location':'NIEUWE KLANT',
            'reference_location':None,'status':'UNMATCHED_LOCATION'}],
        'summary':{},'source_manifest':[{'row':2,'planet_id':'100'}],
        'movements':[{'id':1,'planet_id':'100','day':'2026-08-12','source_location':'NIEUWE KLANT',
            'location':None,'employee_status':'MATCHED','location_status':'UNMATCHED_LOCATION',
            'status':'UNMATCHED_LOCATION','routes':[],
            'source_shifts':[{'row':2,'customer':'NIEUWE KLANT'}]}]}
    with store.transaction() as db:
        run=db.execute('INSERT INTO matching_runs(month,created_at,source_path,payload) VALUES(?,?,?,?)',
            ('2026-08','2026-09-01T00:00:00+00:00','unused.xlsx',json.dumps(payload))).lastrowid
    monkeypatch.setattr(store,'process_matching_file',lambda db,source,expected_hash=None:[{'month':'2026-08'}])
    return store,run,worker


def base(run):
    return {'run_id':run,'source_location':'NIEUWE KLANT','choice':'EXISTING','location':'LUCHTHAVEN',
        'valid_from':'2026-08-12','reason':'Nieuwe klant bevestigd','address':{}}


def test_customer_can_link_to_existing_location_atomically(tmp_path,monkeypatch):
    store,run,worker=prepared(tmp_path,monkeypatch)
    result=store.apply('customer_onboard',base(run),store.snapshot()['revision'])
    assert result=={'location':'LUCHTHAVEN','customers':1,'routes':0,'months':1,'new_location':False}
    state=store.snapshot()
    assert any(link['customer']=='nieuwe klant' and link['location']=='LUCHTHAVEN' for link in state['location_links'])
    assert len([route for route in state['routes'] if route['worker_id']==worker])==1


def test_new_location_saves_address_and_default_routes(tmp_path,monkeypatch):
    store,run,worker=prepared(tmp_path,monkeypatch);data=base(run)
    data.update(choice='NEW',location='Nieuwe Hub',address={
        'street':'Havenlaan','number':'10','unit':'','postal_code':'1000','city':'Brussel','country':'BE'})
    result=store.apply('customer_onboard',data,store.snapshot()['revision'])
    assert result['new_location'] and result['routes']==1
    state=store.snapshot();location=next(row for row in state['location_addresses'] if row['location']=='Nieuwe Hub')
    assert location['address']['street']=='Havenlaan' and location['valid_from']=='2026-08-12'
    route=next(row for row in state['routes'] if row['worker_id']==worker and row['location']=='Nieuwe Hub')
    assert route['mode']=='Privé auto'
    default=next(row for row in state['transport_defaults'] if row['worker_id']==worker and row['location']=='Nieuwe Hub')
    assert default['mode']=='Privé auto' and default['valid_from']=='2026-08-12'


def test_new_location_failure_rolls_back_links_routes_and_address(tmp_path,monkeypatch):
    store,run,worker=prepared(tmp_path,monkeypatch);before=store.snapshot();data=base(run)
    data.update(choice='NEW',location='Nieuwe Hub',address={
        'street':'Havenlaan','number':'10','unit':'','postal_code':'1000','city':'Brussel','country':''})
    with pytest.raises(ValueError,match='volledige locatieadres'):
        store.apply('customer_onboard',data,before['revision'])
    after=store.snapshot()
    assert after['location_links']==before['location_links']
    assert after['routes']==before['routes']
    assert after['location_addresses']==before['location_addresses']


def test_customer_onboarding_rejects_existing_name_as_new(tmp_path,monkeypatch):
    store,run,_=prepared(tmp_path,monkeypatch);data=base(run)
    data.update(choice='NEW',location='LUCHTHAVEN',address={
        'street':'Test','number':'1','unit':'','postal_code':'1000','city':'Brussel','country':'BE'})
    with pytest.raises(ValueError,match='bestaat al'):
        store.apply('customer_onboard',data,store.snapshot()['revision'])
