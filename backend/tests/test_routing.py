import json
import pytest
from app import routing, geocoding
from app.configuration.routes import RouteStore
from app.configuration.addresses import append_address
from app.matching import configuration_digest


def prepared(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    a=dict(street='Teststraat',number='12',unit='',postal_code='1000',city='Brussel',country='BE')
    with store.transaction() as db:
        wid=store.worker(db,'Fictief Voorbeeld')
        append_address(db,wid,'2026-01-01',a,'Test')
        db.execute('INSERT INTO location_address_versions(location_key,location,valid_from,address,changed_at,reason) VALUES(?,?,?,?,?,?)',
                   ('luchthaven','LUCHTHAVEN','2026-01-01',json.dumps({**a,'number':'99'}),'test','Test'))
        for addr,status in [(a,'CONFIRMED'),({**a,'number':'99'},'REVIEW')]:
            db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at) VALUES(?,?,?,?,?)',
                       (geocoding.fingerprint(addr),'mapbox-v6-permanent',status,json.dumps({'longitude':4.3,'latitude':50.8}),'test'))
    config=store.snapshot()
    payload={'source_sha256':'fictional-source','month':'2026-08','created_at':'test','configuration_digest':configuration_digest(config),
             'agents':[{'planet_id':'006','worker_id':wid}],
             'movements':[{'planet_id':'006','day':'2026-08-01','location':'LUCHTHAVEN','source_location':'TUI','status':'MATCHED',
                          'routes':[{'mode':'Auto'},{'mode':'Fiets'},{'mode':'Trein'}]}]}
    with store.transaction() as db:run=store.insert_matching(db,payload,'/fictional.xlsx')
    return store,run,payload,wid,a


def test_plan_only_export_profiles_deduplicated(tmp_path):
    store,run,payload,_,_=prepared(tmp_path)
    with store.transaction() as db:
        later={**payload,'month':'2026-09','movements':[{**payload['movements'][0],'day':'2026-09-01'}]}
        store.insert_matching(db,later,'/fictional.xlsx')
    plan=store.get_route_plan(run)
    assert plan['months']==['2026-08','2026-09']
    assert len(plan['routes'])==2 and plan['new_requests']==2
    assert {r['profile'] for r in plan['routes']}=={'driving','cycling'}
    assert plan['excluded']==2
    assert all(len(r['contexts'])==2 for r in plan['routes'])


def test_request_once_pending_committed_and_modes_separate(tmp_path,monkeypatch):
    store,run,_,_,_=prepared(tmp_path);calls=[]
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    def request(mode,origin,dest):
        with store.connect() as db:assert db.execute('SELECT count(*) FROM route_distances WHERE status=?',('PENDING',)).fetchone()[0]==1
        calls.append(mode);return routing.parse_response({'code':'Ok','routes':[{'distance':19000.5},{'distance':17500.25}]})
    monkeypatch.setattr(routing,'request_distance',request)
    for route in store.get_route_plan(run)['routes']:
        for _ in range(2):store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    assert sorted(calls)==['cycling','driving']
    assert all(r['kms']=='18' for r in store.snapshot()['route_distances'])
    with store.connect() as db:assert all(r[0]=='17.50025' for r in db.execute('SELECT kms FROM route_distances'))
    assert store.get_route_plan(run)['new_requests']==0


def test_failure_or_crash_never_automatic_retry(tmp_path,monkeypatch):
    store,run,_,_,_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    def crash(*args):raise RuntimeError('simulated process interruption')
    monkeypatch.setattr(routing,'request_distance',crash)
    route=store.get_route_plan(run)['routes'][0];data={'run_id':run,'cache_key':route['cache_key'],'consent':True}
    with pytest.raises(RuntimeError):store.apply('route_distance_request',data,store.snapshot()['revision'])
    assert store.snapshot()['route_distances'][0]['status']=='PENDING'
    store.apply('route_distance_request',data,store.snapshot()['revision'])
    assert len(store.snapshot()['route_distances'])==1


def test_address_dates_keep_old_routes(tmp_path):
    store,run,payload,wid,a=prepared(tmp_path)
    with store.transaction() as db:append_address(db,wid,'2026-09-01',{**a,'number':'88'},'Verhuis')
    with store.transaction() as db:store.insert_matching(db,{**payload,'month':'2026-09','movements':[{**payload['movements'][0],'day':'2026-09-01'}]},'/fictional.xlsx')
    plan=store.get_route_plan(run)
    assert len(plan['routes'])==2
    assert all(c['day']=='2026-08-01' for r in plan['routes'] for c in r['contexts'])
    assert len(plan['blocked'])==2


def test_stale_mapping_consent_and_revision_guard(tmp_path,monkeypatch):
    store,run,_,wid,_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    route=store.get_route_plan(run)['routes'][0]
    data={'run_id':run,'cache_key':route['cache_key'],'consent':True}
    with pytest.raises(ValueError):store.apply('route_distance_request',{**data,'consent':False},store.snapshot()['revision'])
    with pytest.raises(ValueError):store.apply('route_distance_request',data,store.snapshot()['revision']-1)
    assert not store.snapshot()['route_distances']
    store.apply('worker_rename',{'worker_id':wid,'name':'Gewijzigd Voorbeeld'},store.snapshot()['revision'])
    with pytest.raises(ValueError):store.get_route_plan(run)


@pytest.mark.parametrize('payload',[{'code':'NoRoute'}, {'code':'Ok','routes':[{'distance':-1}]},
                                  {'code':'Ok','routes':[{'distance':float('nan')}]},
                                  {'code':'Ok','routes':[{'distance':True}]}])
def test_invalid_distance_not_zero(payload):
    with pytest.raises(ValueError):routing.parse_response(payload)


def test_request_profile_alternatives_no_traffic_or_identity(monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    captured=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"code":"Ok","routes":[{"distance":1234.5,"geometry":{"type":"LineString","coordinates":[[4.3,50.8],[4.4,50.9]]}}]}'
    class Opener:
        def open(self,url,timeout):captured.append(url);return Response()
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'build_opener',lambda *args:Opener())
    assert routing.request_distance('cycling',(4.3,50.8),(4.4,50.9))['kms']=='1.2345'
    url=urlsplit(captured[0]);query=parse_qs(url.query)
    assert '/mapbox/cycling/' in url.path and 'traffic' not in captured[0]
    assert query=={'access_token':['pk.fake'],'alternatives':['true'],'overview':['full'],'geometries':['geojson'],'steps':['false']}
