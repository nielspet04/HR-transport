import pytest
from app.route_corrections import effective_distance
from app.distance_export import export_rows
from test_distance_export import export_fixture


def test_correct_restore_preserve_original_and_persist(tmp_path,monkeypatch):
    store,run=export_fixture(tmp_path,monkeypatch)
    row=store.snapshot()['route_distances'][0]
    wid=store.snapshot()['workers'][0]['id']
    data={'route_id':row['id'],'worker_id':wid,'kms':'12','reason':'HR controleert correcte route'}
    store.apply('route_distance_override',data,store.snapshot()['revision'])
    from app.configuration.routes import RouteStore
    store=RouteStore(store.path)
    saved=store.snapshot()['route_distances'][0]
    assert saved['kms']=='18' and effective_distance(saved,wid)['kms']=='12'
    assert effective_distance(saved,wid+999)['kms']=='18'
    distances,shifts,_=export_rows(store,run)
    assert distances[0][2]==12 and distances[0][4]=='HR-CORRECTIE'
    assert all(r[2]==12 and r[9].startswith('HR-CORRECTIE') for r in shifts if r[1]=='Auto')
    assert all(r[2] is None for r in shifts if r[1]=='Fiets')
    store.apply('route_distance_override',{**data,'reset':True,'reason':'Terug naar Mapbox'},store.snapshot()['revision'])
    restored=store.snapshot()['route_distances'][0]
    assert not restored['overrides'] and len(restored['correction_history'])==2
    assert effective_distance(restored,wid)['kms']=='18'
    with store.connect() as db:assert db.execute('SELECT kms FROM route_distances').fetchone()[0]=='17.0001'


@pytest.mark.parametrize('value',['12.2','-1',True,None,'NaN','',100001])
def test_invalid_correction_rejected(tmp_path,monkeypatch,value):
    store,run=export_fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError):store.apply('route_distance_override',{'route_id':1,'worker_id':1,'kms':value,'reason':'Test'},store.snapshot()['revision'])
    assert not store.snapshot()['route_distances'][0]['correction_history']


def test_reason_and_ownership_required(tmp_path,monkeypatch):
    store,run=export_fixture(tmp_path,monkeypatch)
    for data in [{'route_id':1,'worker_id':1,'kms':12,'reason':''},{'route_id':1,'worker_id':999,'kms':12,'reason':'Test'}]:
        with pytest.raises(ValueError):store.apply('route_distance_override',data,store.snapshot()['revision'])
