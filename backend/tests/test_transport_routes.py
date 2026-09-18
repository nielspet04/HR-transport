"""Simplified phase 3: source-only routes, bike/car distances and manual edit."""
import json
from pathlib import Path
import os
import http.client
import threading
import pytest
from app.configuration.routes import RouteStore
from app.configuration.store import Store
from app.importers.reference import import_reference, HEADERS
from test_planet_importer import write_xlsx


def source(tmp_path,rows):
    path=write_xlsx(tmp_path/'source.xlsx',[list(HEADERS),*rows],sheet_name='Niels')
    return import_reference(path,sheet_name='Niels',route_aware=True)


def apply(store,action,**data):store.apply(action,data,store.snapshot()['revision'])


def test_new_sheet_only_four_fields_and_modes_are_separate(tmp_path):
    data=source(tmp_path,[['Test Alex','APT',25,'Privé auto'],['Test Alex','APT Fiets',21,'Fiets'],['Test Alex','APT',25,'Privé auto']])
    assert not data.records[0].unresolved and not data.records[1].unresolved
    store=RouteStore(tmp_path/'routes.sqlite3');report=store.import_source(data,'2026-02-01')
    assert report=={'source_rows':3,'routes':2,'duplicates':1,'review':0,'workers':1}
    assert {r['location'] for r in store.snapshot()['routes']}=={'LUCHTHAVEN'}
    assert store.resolve(1,'2026-08-01')['kms']=='25'
    assert store.resolve(2,'2026-08-01')['kms']=='21'
    assert json.loads(store.snapshot()['routes'][0]['source_rows'])==[2,4]
    assert tuple(dict(data.records[0].source_values))==HEADERS


def test_source_band_conflicts_and_unknown_modes_remain_visible(tmp_path):
    data=source(tmp_path,[['A','Redu','37-39','Auto'],['A','APT',20,'Mob budget'],['B','APT',10,'Fiets'],['B','APT Fiets',11,'Fiets']])
    store=RouteStore(tmp_path/'routes.sqlite3');report=store.import_source(data,'2026-02-01')
    assert report['review']==2 and report['routes']==3
    assert store.snapshot()['routes'][0]['mode']=='Auto'
    assert store.resolve(1,'2026-08-01')['raw_distance']=='37-39'
    assert store.resolve(3,'2026-08-01')['kms'] is None


def test_manual_route_add_and_edit_persist_and_import_is_idempotent(tmp_path):
    path=tmp_path/'routes.sqlite3';store=RouteStore(path)
    data=source(tmp_path,[['A','APT',12,'Fiets']]);store.import_source(data,'2026-02-01')
    apply(store,'route_update',route_id=1,kms='18,5',valid_from='2026-09-01',reason='Verhuisd')
    assert store.import_source(data,'2026-02-01')['already_imported']
    assert store.resolve(1,'2026-08-31')['kms']=='12'
    assert RouteStore(path).resolve(1,'2026-09-01')['kms']=='18.5'
    apply(store,'route_add',name='New',location='Postnl Test',mode='Privé auto',kms='0',valid_from='2026-09-01',reason='Nieuw')
    apply(store,'worker_rename',worker_id=2,name='New Name')
    assert store.snapshot()['workers'][1]['name']=='New Name'
    assert len(store.snapshot()['routes'])==2


def test_same_date_correction_is_audited_and_keeps_earlier_versions(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3');store.import_source(source(tmp_path,[['A','APT',12,'Fiets']]),'2026-02-01')
    apply(store,'route_update',route_id=1,kms='20',valid_from='2026-09-01',reason='Verhuisd')
    apply(store,'route_update',route_id=1,kms='21',valid_from='2026-09-01',reason='Meetfout')
    assert store.resolve(1,'2026-08-31')['kms']=='12'
    assert store.resolve(1,'2026-09-01')['kms']=='21'
    with store.connect() as db:
        change=db.execute('SELECT * FROM corrections').fetchone()
        assert json.loads(change['previous'])['kms']=='20' and change['reason']=='Meetfout'


def test_relocation_all_routes_atomic_and_stale_screen_rejected(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3');store.import_source(source(tmp_path,[['A','APT',12,'Fiets'],['A','APT',15,'Privé auto']]),'2026-02-01')
    before=store.snapshot()
    with pytest.raises(ValueError):apply(store,'worker_move',worker_id=1,valid_from='2026-09-01',reason='Move',updates=[{'route_id':1,'kms':'20'}])
    with pytest.raises(ValueError):apply(store,'worker_move',worker_id=1,valid_from='2026-09-01',reason='Move',updates=[{'route_id':1,'kms':'20'},{'route_id':2,'kms':'-1'}])
    assert store.snapshot()==before
    with pytest.raises(ValueError):store.apply('route_update',{'route_id':1,'kms':'20','valid_from':'2026-09-01','reason':'Move'},0)
    apply(store,'worker_move',worker_id=1,valid_from='2026-09-01',reason='Move',updates=[{'route_id':1,'kms':'20'},{'route_id':2,'kms':'24'}])
    assert store.resolve(1,'2026-09-01')['kms']=='20' and store.resolve(2,'2026-09-01')['kms']=='24'


def test_legacy_db_and_incomplete_import_are_untouched(tmp_path):
    legacy=Store(tmp_path/'legacy.sqlite3');before=legacy.snapshot()
    store=RouteStore(tmp_path/'routes.sqlite3')
    with pytest.raises(ValueError):store.import_source(source(tmp_path,[[None,'APT',12,'Fiets']]),'2026-02-01')
    assert not store.snapshot()['routes'] and legacy.snapshot()==before


def test_route_http_interface_and_update(tmp_path):
    from app.configuration.server import make_server
    store=RouteStore(tmp_path/'routes.sqlite3');store.import_source(source(tmp_path,[['Demo Alex','APT',12,'Fiets']]),'2026-02-01')
    server=make_server(store,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request('GET','/');response=client.getresponse();assert response.status==200;assert b'/routes.js' in response.read()
        client.request('GET','/routes.js');response=client.getresponse();assert response.status==200;response.read()
        client.request('GET','/api/state');response=client.getresponse();state=json.loads(response.read());assert state['view']=='routes'
        body=json.dumps({'revision':state['revision'],'data':{'route_id':1,'kms':'18','valid_from':'2026-09-01','reason':'Demo verhuizing'}})
        client.request('POST','/api/action/route_update',body,{'Content-Type':'application/json','X-CSRF-Token':state['csrf']})
        response=client.getresponse();assert response.status==200;response.read()
        assert store.resolve(1,'2026-09-01')['kms']=='18'
    finally:
        client.close();server.shutdown();server.server_close();thread.join(timeout=5)


@pytest.mark.skipif(not os.environ.get('NEW_REFERENCE_SOURCE'),reason='Private optional new reference')
def test_private_new_reference_counts(tmp_path):
    data=import_reference(os.environ['NEW_REFERENCE_SOURCE'],sheet_name='Niels',route_aware=True)
    store=RouteStore(tmp_path/'routes.sqlite3');report=store.import_source(data,'2026-02-01')
    assert report=={'source_rows':146,'routes':143,'duplicates':3,'review':1,'workers':62}
