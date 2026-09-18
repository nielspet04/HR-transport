import json
import pytest
from app import automatic_routes,routing,geocoding
from app.configuration.addresses import append_address
from test_routing import prepared
from test_itinerary import multi_case
from test_cached_calculation import calculate


def enable(store):
    with store.transaction() as db:db.execute('UPDATE automatic_route_settings SET enabled=1')


def test_automatic_new_address_confirm_and_routes_once(tmp_path,monkeypatch):
    store,run,p,wid,addr=prepared(tmp_path)
    new={**addr,'number':'45'}
    with store.transaction() as db:append_address(db,wid,'2026-07-01',new,'Verhuizing')
    enable(store);calls=[]
    monkeypatch.setattr(geocoding,'configured',lambda:True)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    def geocode(address):
        with store.connect() as db:assert db.execute('SELECT status FROM address_geocodes WHERE address_hash=?',(geocoding.fingerprint(new),)).fetchone()[0]=='PENDING'
        calls.append('geocode');return {'status':'REVIEW','eligible':True,'longitude':4.5,'latitude':50.8}
    monkeypatch.setattr(geocoding,'request_address',geocode)
    monkeypatch.setattr(routing,'request_distance',lambda *a:(calls.append(a[0]) or {'meters':'5100','kms':'5.1','alternatives_count':1}))
    result=automatic_routes.run(store)
    assert result['geocoded']==1 and result['routes']==2
    assert sorted(calls)==['cycling','driving','geocode']
    assert automatic_routes.run(store)['routes']==0 and len(calls)==3
    with store.connect() as db:assert db.execute('SELECT status FROM address_geocodes WHERE address_hash=?',(geocoding.fingerprint(new),)).fetchone()[0]=='CONFIRMED'


def test_uncertain_geocode_blocks_not_retried(tmp_path,monkeypatch):
    store,run,p,wid,addr=prepared(tmp_path)
    new={**addr,'number':'45'}
    with store.transaction() as db:append_address(db,wid,'2026-07-01',new,'Verhuizing')
    enable(store);calls=[]
    monkeypatch.setattr(geocoding,'configured',lambda:True)
    monkeypatch.setattr(geocoding,'request_address',lambda a:(calls.append(a) or {'status':'REVIEW','eligible':False,'longitude':4.5,'latitude':50.8}))
    monkeypatch.setattr(routing,'request_distance',lambda *a:pytest.fail('Uncertain coordinates must not route'))
    assert automatic_routes.run(store)['routes']==0
    automatic_routes.run(store);assert len(calls)==1
    assert store.get_route_plan(run)['blocked']


def test_auto_transfers_saved_shared_correction_and_personal_priority(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    enable(store);calls=[]
    monkeypatch.setattr(geocoding,'configured',lambda:True)
    monkeypatch.setattr(routing,'request_distance',lambda *a:(calls.append(a) or {'meters':'6100','kms':'6.1','alternatives_count':1}))
    result=automatic_routes.run(store)
    assert result['routes']>=1
    transfer=store.snapshot()['location_transfers'][0]
    assert transfer['cached']['status']=='READY'
    assert calculate(store,run,p)['rows'][1]['distance']=='7'
    rid=transfer['cached']['id']
    store.apply('location_transfer_override',{'route_id':rid,'kms':10,'reason':'Verkeerde weg'},store.snapshot()['revision'])
    assert calculate(store,run,p)['rows'][1]['amount']=='5.32'
    store.apply('route_distance_override',{'route_id':rid,'worker_id':wid,'kms':12,'reason':'Persoonlijk'},store.snapshot()['revision'])
    assert calculate(store,run,p)['rows'][1]['distance']=='12'
    store.apply('location_transfer_override',{'route_id':rid,'reset':True,'reason':'Herstellen'},store.snapshot()['revision'])
    assert calculate(store,run,p)['rows'][1]['distance']=='12'
    old=len(calls);automatic_routes.run(store);assert len(calls)==old


def test_disabled_never_calls_mapbox(tmp_path,monkeypatch):
    store,*_=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'configured',lambda:pytest.fail('Disabled workflow must not inspect token'))
    assert automatic_routes.run(store)['routes']==0
