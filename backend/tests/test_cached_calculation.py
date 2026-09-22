from copy import deepcopy
import json
from app import routing
from app.calculation import pdf_start_tariff
from app.cached_calculation import calculate_cached_month
from app.matching import configuration_digest
from test_routing import prepared


def setup_case(tmp_path,monkeypatch,cached=True):
    store,run,p,wid,_=prepared(tmp_path)
    with store.transaction() as db:
        db.execute('INSERT INTO car_tariffs(valid_from,data,source,reason,changed_at) VALUES(?,?,?,?,?)',('2026-01-01',json.dumps(pdf_start_tariff()),'Test','Test','test'))
        p['movements'][0].update(id=1,phase5_special=False)
        for i,r in enumerate(p['movements'][0]['routes'],1):r.update(route_id=i,valid_from='2026-01-01',kms='999')
        p['configuration_digest']=configuration_digest(store.matching_config(db))
        p['calculation']={}
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'meters':'17001','kms':'17.001','alternatives_count':1})
    if cached:
        route=next(r for r in store.get_route_plan(run)['routes'] if r['profile']=='driving')
        store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    return store,run,p,wid


def calculate(store,run,p):
    with store.connect() as db:return calculate_cached_month(db,store.matching_config(db),run,p)


def test_auto_default_cached_not_manual_train_or_bike(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    monkeypatch.setattr(routing,'request_distance',lambda *a:(_ for _ in ()).throw(AssertionError('No requests during calculation')))
    before=deepcopy(p)
    row=calculate(store,run,p)['rows'][0]
    assert row['status']=='CALCULATED' and row['distance']=='18' and row['amount']=='7.38'
    assert row['selected_mode']=='Auto' and row['distance_source']=='Mapbox'
    assert p==before
    assert store.get_matching(run)['calculation']['rows'][0]['amount']=='7.38'


def test_payroll_ready_requires_month_and_external_reference(tmp_path,monkeypatch):
    from app.configuration.external_references import append_reference
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    assert not store.get_matching(run)['calculation']['payroll_ready']
    with store.transaction() as db:append_reference(db,wid,'2026-01-01','00123','Test')
    assert store.get_matching(run)['calculation']['payroll_ready']


def test_hr_override_recalculates_and_reset(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    data={'route_id':store.snapshot()['route_distances'][0]['id'],'worker_id':wid,'kms':10,'reason':'HR gecontroleerd'}
    store.apply('route_distance_override',data,store.snapshot()['revision'])
    row=store.get_matching(run)['calculation']['rows'][0]
    assert row['distance']=='10' and row['amount']=='5.32' and row['distance_source']=='HR'
    store.apply('route_distance_override',{**data,'reset':True},store.snapshot()['revision'])
    assert store.get_matching(run)['calculation']['rows'][0]['amount']=='7.38'


def test_missing_cache_never_fallback(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch,cached=False)
    row=calculate(store,run,p)['rows'][0]
    assert row['status']=='BLOCKED' and row['amount'] is None


def test_special_multilocation_and_bike_only_not_paid(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    special=deepcopy(p);special['movements'][0]['phase5_special']=True
    assert calculate(store,run,special)['rows'][0]['status']=='BLOCKED'
    multi=deepcopy(p);multi['movements'].append({**multi['movements'][0],'id':2,'location':'Other','source_location':'Other'})
    assert all(r['status']=='LATER_PHASE' and r['amount'] is None for r in calculate(store,run,multi)['rows'])
    bike=deepcopy(p);bike['movements'][0]['routes']=[bike['movements'][0]['routes'][1]]
    assert calculate(store,run,bike)['rows'][0]['amount'] is None
    train=deepcopy(p);train['movements'][0]['routes']=[train['movements'][0]['routes'][2]]
    assert calculate(store,run,train)['rows'][0]['status']=='EXCLUDED_TRAIN'


def test_relocation_invalid_coordinates_stale_config_and_tariff_date(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    with store.transaction() as db:db.execute('UPDATE address_geocodes SET status=? WHERE status=?',('ERROR','CONFIRMED'))
    assert calculate(store,run,p)['rows'][0]['amount'] is None
    with store.transaction() as db:
        db.execute('UPDATE address_geocodes SET status=? WHERE status=?',('CONFIRMED','ERROR'))
        db.execute('UPDATE car_tariffs SET valid_from=?',('2026-09-01',))
    assert calculate(store,run,p)['rows'][0]['amount'] is None
