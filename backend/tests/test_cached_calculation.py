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


def test_changed_default_immediately_replaces_stored_import_route(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    location=p['movements'][0]['location']
    store.apply('transport_default',{'worker_id':wid,'location':location,
        'mode':'Dienstwagen','valid_from':'2026-02-01','reason':'Dienstwagen bevestigd'},
        store.snapshot()['revision'])
    matching=store.get_matching(run)
    movement=matching['movements'][0]
    row=matching['calculation']['rows'][0]
    assert [route['mode'] for route in movement['routes']]==['Dienstwagen']
    assert row['status']=='EXCLUDED_COMPANY_CAR'
    assert row['selected_mode']=='Dienstwagen' and row['amount'] is None


def test_one_shift_changed_from_car_to_bicycle_requests_separate_cycling_route(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    driving=next(item for item in store.snapshot()['route_distances'] if item['profile']=='driving')
    store.apply('shift_transport_choice',{'run_id':run,'movement_id':1,
        'mode':'BIKE','reason':'Deze shift uitzonderlijk met de fiets'},store.snapshot()['revision'])
    cycling=next(item for item in store.get_route_plan(run)['routes'] if item['profile']=='cycling')
    assert cycling['cache_key']!=driving['cache_key'] and cycling['cached'] is None
    blocked=store.get_matching(run)['calculation']['rows'][0]
    assert blocked['status']=='BLOCKED' and blocked['amount'] is None
    assert blocked['reason']=='Geen bevestigde opgeslagen fietsroute op deze datum.'
    calls=[]
    monkeypatch.setattr(routing,'request_distance',lambda profile,*args:
        (calls.append(profile) or {'meters':'8100','kms':'8.1','alternatives_count':1}))
    store.apply('route_distance_request',{'run_id':run,'cache_key':cycling['cache_key'],'consent':True},store.snapshot()['revision'])
    calculated=store.get_matching(run)['calculation']['rows'][0]
    assert calls==['cycling']
    assert calculated['status']=='CALCULATED' and calculated['selected_mode']=='Fiets'
    assert calculated['distance']=='9' and calculated['distance_source']=='Mapbox'
    assert calculated['mapbox_route_id']!=driving['id']


def test_one_wrong_planet_shift_location_can_be_corrected_and_restored(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    airport_route=next(item for item in store.snapshot()['route_distances'] if item['profile']=='driving')
    other_address={'street':'Andere site','number':'2','unit':'','postal_code':'1000','city':'Brussel','country':'BE'}
    with store.transaction() as db:
        db.execute('INSERT INTO location_address_versions(location_key,location,valid_from,address,changed_at,reason) VALUES(?,?,?,?,?,?)',
            ('other','Other','2026-01-01',json.dumps(other_address),'test','Test'))
        from app import geocoding
        db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at) VALUES(?,?,?,?,?)',
            (geocoding.fingerprint(other_address),'mapbox-v6-permanent','REVIEW',json.dumps({'longitude':4.5,'latitude':50.9}),'test'))
        route_id=db.execute('INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,?,?,?,?)',
            (wid,'Other','other','Privé auto','privé auto')).lastrowid
        store.version(db,route_id,'2026-01-01',None,'Test',allow_missing=True)
        db.execute('INSERT INTO transport_defaults(worker_id,location,location_key,mode,valid_from,reason,changed_at) VALUES(?,?,?,?,?,?,?)',
            (wid,'Other','other','Privé auto','2026-01-01','Test','test'))
        p['configuration_digest']=configuration_digest(store.matching_config(db))
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    store.apply('shift_location_choice',{'run_id':run,'movement_id':1,
        'location':'Other','reason':'Foutieve Pl@net-locatie'},store.snapshot()['revision'])
    corrected=store.get_matching(run)
    movement=corrected['movements'][0];row=corrected['calculation']['rows'][0]
    assert movement['location']=='Other' and movement['original_location']=='LUCHTHAVEN'
    assert movement['location_corrected'] is True and row['status']=='BLOCKED'
    other_route=next(item for item in store.get_route_plan(run)['routes'] if item['profile']=='driving')
    assert other_route['cache_key']!=airport_route['cache_key'] and other_route['cached'] is None
    monkeypatch.setattr(routing,'request_distance',lambda *args:
        {'meters':'12300','kms':'12.3','alternatives_count':1})
    store.apply('route_distance_request',{'run_id':run,'cache_key':other_route['cache_key'],'consent':True},store.snapshot()['revision'])
    recalculated=store.get_matching(run)
    assert recalculated['calculation']['rows'][0]['distance']=='13'
    assert recalculated['calculation']['monthly']['employees'][0]['shifts'][0]['location']=='Other'
    store.apply('shift_location_choice',{'run_id':run,'movement_id':1,'reset':True,
        'reason':'Oorspronkelijke locatie herstellen'},store.snapshot()['revision'])
    restored=store.get_matching(run)
    assert restored['movements'][0]['location']=='LUCHTHAVEN'
    assert restored['calculation']['rows'][0]['mapbox_route_id']==airport_route['id']


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
