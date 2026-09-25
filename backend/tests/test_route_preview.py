import json
import pytest
from app import routing, route_preview
from test_routing import prepared

LINE={'type':'LineString','coordinates':[[4.3,50.8],[4.4,50.9],[4.5,51.0]]}


def test_selected_alternative_geometry():
    result=routing.parse_response({'code':'Ok','routes':[{'distance':2000,'geometry':{**LINE,'coordinates':[[4,50],[5,51]]}},{'distance':1000,'geometry':LINE}]})
    assert result['geometry']==LINE and result['kms']=='1'


def test_existing_distance_unchanged_and_preview_once(tmp_path,monkeypatch):
    store,run,*_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'meters':'1000','kms':'1','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    rid=store.snapshot()['route_distances'][0]['id'];calls=[]
    def request(*args):
        with store.connect() as db:assert db.execute('SELECT status FROM route_visualizations WHERE route_id=?',(rid,)).fetchone()[0]=='PENDING'
        calls.append(args);return {'geometry':LINE,'kms':'1.2'}
    monkeypatch.setattr(routing,'request_distance',request)
    for _ in range(2):store.apply('route_visualization_request',{'route_id':rid,'consent':True},store.snapshot()['revision'])
    assert len(calls)==1 and store.snapshot()['route_distances'][0]['kms']=='1'
    view=route_preview.preview(store,rid)
    assert view['kms']=='2' and view['original_kms']=='1'
    assert all(40 <= x <= 860 and 40 <= y <= 560 for x,y in view['points'])
    assert 'geometry' not in view


def test_future_request_saves_geometry_without_extra_call(tmp_path,monkeypatch):
    store,run,*_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'geometry':LINE,'meters':'1000','kms':'1','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    rid=store.snapshot()['route_distances'][0]['id']
    assert route_preview.preview(store,rid)['status']=='READY'


def test_catalog_links_saved_geometry_without_exposing_addresses(tmp_path,monkeypatch):
    store,run,_,wid,_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'geometry':LINE,'meters':'17500','kms':'17.5','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    item=store.snapshot()['route_maps'][0]
    assert item['worker_id']==wid and item['location_key']=='luchthaven'
    assert item['kms']=='18' and item['visual_status']=='READY'
    assert 'geometry' not in item and 'origin_hash' not in item and 'destination_hash' not in item


def test_catalog_recovers_context_for_legacy_cached_route(tmp_path,monkeypatch):
    store,run,_,wid,_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'geometry':LINE,'meters':'9000','kms':'9','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    store.apply('route_add',{'name':'Fictief Voorbeeld','location':'LUCHTHAVEN','mode':'Auto','kms':'9','valid_from':'2026-01-01','reason':'Test'},store.snapshot()['revision'])
    with store.transaction() as db: db.execute('DELETE FROM route_saved_contexts')
    assert any(item['worker_id']==wid and item['location_key']=='luchthaven' for item in store.snapshot()['route_maps'])


def test_real_map_background_is_cached_and_budgeted(tmp_path,monkeypatch):
    store,run,*_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'geometry':LINE,'meters':'9000','kms':'9','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    rid=store.snapshot()['route_distances'][0]['id'];calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def read(self,_): calls.append(1);return b'\x89PNG\r\n\x1a\nmap'
    class Opener:
        def open(self,*_,**__): return Response()
    monkeypatch.setattr(route_preview,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(route_preview,'build_opener',lambda *_:Opener())
    assert route_preview.background(store,rid).startswith(b'\x89PNG')
    assert route_preview.background(store,rid).startswith(b'\x89PNG')
    assert len(calls)==1
    with store.connect() as db: assert db.execute('SELECT requests FROM route_map_usage').fetchone()[0]==1


@pytest.mark.parametrize('line',[None,{'type':'Point','coordinates':[4,50]}, {'type':'LineString','coordinates':[[4,50],[True,51]]}, {'type':'LineString','coordinates':[[4,50],[4,float('nan')]]}])
def test_invalid_geometry(line):
    with pytest.raises(ValueError):routing.validate_geometry(line)


def test_preview_crash_blocks_repeat(tmp_path,monkeypatch):
    store,run,*_=prepared(tmp_path)
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'meters':'1000','kms':'1','alternatives_count':1})
    route=store.get_route_plan(run)['routes'][0]
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    rid=store.snapshot()['route_distances'][0]['id']
    def crash(*a):raise RuntimeError('crash')
    monkeypatch.setattr(routing,'request_distance',crash)
    with pytest.raises(RuntimeError):store.apply('route_visualization_request',{'route_id':rid,'consent':True},store.snapshot()['revision'])
    store.apply('route_visualization_request',{'route_id':rid,'consent':True},store.snapshot()['revision'])
    assert route_preview.preview(store,rid)['status']=='PENDING'
