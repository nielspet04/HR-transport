from app.transport_defaults import effective
from app.configuration.routes import RouteStore
from test_matching import config,imported,RULES,shift
from app.matching import match_import


def test_dated_default_replaces_route_modes_without_deleting_them():
    c=config();c['transport_defaults']=[{'id':1,'worker_id':1,'location':'LUCHTHAVEN','location_key':'luchthaven','mode':'Mob budget','valid_from':'2026-08-01','reason':'HR','changed_at':'x'}]
    result=match_import(imported(shift(customer='TUI')),c,RULES)
    movement=result['movements'][0]
    assert movement['status']=='MATCHED'
    assert [r['mode'] for r in movement['routes']]==['Mob budget']
    assert any(r['mode']=='Fiets' for r in c['routes'])


def test_effective_default_is_location_and_date_specific():
    rows=[{'id':1,'worker_id':2,'location_key':'site','valid_from':'2026-01-01','mode':'Trein'},
          {'id':2,'worker_id':2,'location_key':'site','valid_from':'2026-09-01','mode':'Fiets'},
          {'id':3,'worker_id':3,'location_key':'site','valid_from':'2026-01-01','mode':'Mob budget'}]
    assert effective(rows,2,'Site','2026-08-01')['mode']=='Trein'
    assert effective(rows,2,'Site','2026-09-01')['mode']=='Fiets'
    assert effective(rows,3,'Site','2026-08-01')['mode']=='Mob budget'


def test_transport_start_date_can_be_saved_at_export_month_start(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Test Agent','location':'Site','mode':'Privé auto',
        'kms':'10','valid_from':'2026-08-14','reason':'Test'},0)
    worker=store.snapshot()['workers'][0]
    store.apply('transport_default',{'worker_id':worker['id'],'location':'Site',
        'mode':'Fiets','valid_from':'2026-08-01','reason':'HR corrigeert ingangsdatum'},
        store.snapshot()['revision'])
    saved=store.snapshot()['transport_defaults'][0]
    assert saved['mode']=='Fiets' and saved['valid_from']=='2026-08-01'


def test_transport_start_also_makes_existing_route_available_from_that_date(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Test Agent','location':'Site','mode':'Privé auto',
        'kms':'17','valid_from':'2026-09-17','reason':'Latere afstand'},0)
    state=store.snapshot();worker=state['workers'][0];route=state['routes'][0]
    store.apply('transport_default',{'worker_id':worker['id'],'location':'Site',
        'mode':'Privé auto','valid_from':'2026-09-01','reason':'Vervoer geldt vanaf maandbegin'},
        state['revision'])
    versions=[item for item in store.snapshot()['versions'] if item['route_id']==route['id']]
    assert sorted((item['valid_from'],item['kms']) for item in versions)==[
        ('2026-09-01',None),('2026-09-17','17')]


def test_new_transport_mode_gets_route_from_same_start_date(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Test Agent','location':'Site','mode':'Privé auto',
        'kms':'17','valid_from':'2026-09-17','reason':'Start'},0)
    worker=store.snapshot()['workers'][0]
    store.apply('transport_default',{'worker_id':worker['id'],'location':'Site',
        'mode':'Fiets','valid_from':'2026-09-01','reason':'Fiets vanaf maandbegin'},
        store.snapshot()['revision'])
    state=store.snapshot();route=next(item for item in state['routes'] if item['mode']=='Fiets')
    version=next(item for item in state['versions'] if item['route_id']==route['id'])
    assert version['valid_from']=='2026-09-01' and version['kms'] is None


def test_transport_edits_do_not_trigger_background_refresh_between_locations(tmp_path,monkeypatch):
    from app import automatic_routes
    calls=[];monkeypatch.setattr(automatic_routes,'trigger',lambda store:calls.append(store))
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Test Agent','location':'Site A','mode':'Privé auto',
        'kms':'10','valid_from':'2026-09-01','reason':'Start'},0)
    calls.clear()
    worker=store.snapshot()['workers'][0]
    store.apply('transport_default',{'worker_id':worker['id'],'location':'Site A',
        'mode':'Dienstwagen','valid_from':'2026-09-01','reason':'Eerste locatie'},
        store.snapshot()['revision'])
    store.apply('transport_default',{'worker_id':worker['id'],'location':'Site B',
        'mode':'Dienstwagen','valid_from':'2026-09-01','reason':'Tweede locatie'},
        store.snapshot()['revision'])
    assert calls==[]
    assert {row['location'] for row in store.snapshot()['transport_defaults']}=={'Site A','Site B'}
