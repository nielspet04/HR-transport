from copy import deepcopy
import json
import pytest
from app.itinerary import itineraries
from app import routing,geocoding
from app.configuration.routes import RouteStore
from test_cached_calculation import setup_case,calculate


def multi_case(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    m=p['movements'][0];m.update(early_late=False,extra_shift_48h=False)
    m['source_shifts']=[{'start':'08:00','end':'12:00','end_day_offset':0,'row':2,'customer':'A'}]
    second=deepcopy(m);second.update(id=2,location='Other',source_location='Other',phase5_special=True,early_late=True,extra_shift_48h=True)
    second['source_shifts']=[{'start':'13:00','end':'17:00','end_day_offset':0,'row':3,'customer':'B'}]
    p['movements'].append(second)
    addr={'street':'Second','number':'1','unit':'','postal_code':'1000','city':'Brussel','country':'BE'}
    with store.transaction() as db:
        db.execute('INSERT INTO location_address_versions(location_key,location,valid_from,address,changed_at,reason) VALUES(?,?,?,?,?,?)',('other','Other','2026-01-01',json.dumps(addr),'test','test'))
        db.execute('INSERT INTO address_geocodes(address_hash,provider,status,result,requested_at) VALUES(?,?,?,?,?)',(geocoding.fingerprint(addr),'mapbox','REVIEW',json.dumps({'longitude':4.8,'latitude':50.9}),'test'))
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    return store,run,p,wid


def test_order_transfer_cached_once_standard_and_override(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    prepared=store.get_route_plan(run)
    transfers=[r for r in prepared['routes'] if r['contexts'][0].get('route_kind')=='TRANSFER']
    assert len(transfers)==1 and transfers[0]['profile']=='driving'
    assert transfers[0]['origin_hash']!=prepared['routes'][0]['origin_hash']
    assert calculate(store,run,p)['rows'][1]['amount'] is None
    calls=[]
    def request(*args):calls.append(args);return {'meters':'6100','kms':'6.1','alternatives_count':1}
    monkeypatch.setattr(routing,'request_distance',request)
    data={'run_id':run,'cache_key':transfers[0]['cache_key'],'consent':True}
    for _ in range(2):store.apply('route_distance_request',data,store.snapshot()['revision'])
    assert len(calls)==1
    rows=calculate(store,run,p)['rows']
    assert rows[0]['distance']=='18' and rows[0]['amount']=='7.38'
    assert rows[1]['distance']=='7' and rows[1]['amount']=='6.06' and rows[1]['tariff_kind']=='EXTRA48'
    assert rows[1]['origin_location']=='LUCHTHAVEN' and all(r['multi_location'] for r in rows)
    cached=next(r for r in store.snapshot()['route_distances'] if r['cache_key']==data['cache_key'])
    store.apply('route_distance_override',{'route_id':cached['id'],'worker_id':wid,'kms':10,'reason':'HR controle'},store.snapshot()['revision'])
    assert calculate(store,run,p)['rows'][1]['amount']=='8.65'
    reverse=deepcopy(p);reverse['movements'].reverse()
    assert itineraries(reverse)[(p['movements'][1]['planet_id'],p['movements'][1]['day'],2)]['origin_location']=='LUCHTHAVEN'


@pytest.mark.parametrize('start,expected_origin,gap',[('14:00','LUCHTHAVEN',120),('14:01',None,121),('18:00',None,360)])
def test_only_gap_up_to_two_hours_is_direct_transfer(tmp_path,monkeypatch,start,expected_origin,gap):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1]['source_shifts'][0].update(start=start,end='23:00')
    leg=itineraries(p)[(p['movements'][1]['planet_id'],p['movements'][1]['day'],2)]
    assert leg['origin_location']==expected_origin and leg['gap_minutes']==gap
    assert leg['journey_kind']==('TRANSFER' if expected_origin else 'HOME')


def test_consecutive_shifts_corrected_to_same_location_use_one_commute(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1].update(location='LUCHTHAVEN',source_location='Wrong source')
    with store.transaction() as db:
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    leg=itineraries(p)[(p['movements'][1]['planet_id'],p['movements'][1]['day'],2)]
    assert leg['same_location_continuation'] is True
    assert leg['journey_kind']=='SAME_LOCATION' and leg['origin_location'] is None
    rows=store.get_matching(run)['calculation']['rows']
    assert rows[0]['status']=='CALCULATED'
    assert rows[1]['status']=='EXCLUDED_SAME_LOCATION' and rows[1]['amount'] is None
    assert store.get_matching(run)['calculation']['monthly']['excluded']==1
    prepared=store.get_route_plan(run)
    assert all(route['origin_hash']!=route['destination_hash'] for route in prepared['routes'])


def test_hr_can_force_direct_transfer_for_gap_over_two_hours(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1]['source_shifts'][0].update(start='18:00',end='23:00')
    with store.transaction() as db:
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    regular=itineraries(p)[(p['movements'][1]['planet_id'],p['movements'][1]['day'],2)]
    assert regular['origin_location'] is None and regular['gap_minutes']==360
    store.apply('itinerary_transfer_override',{'run_id':run,'movement_id':2,
        'direct_transfer':True,'reason':'Agent bleef ter plaatse'},store.snapshot()['revision'])
    shift=next(item for item in store.get_matching(run)['calculation']['monthly']['employees'][0]['shifts']
        if item['movement_id']==2)
    assert shift['origin_location']=='LUCHTHAVEN'
    assert shift['direct_transfer_override'] is True and shift['gap_minutes']==360
    store.apply('itinerary_transfer_override',{'run_id':run,'movement_id':2,
        'direct_transfer':False,'reason':'Thuisrit herstellen'},store.snapshot()['revision'])
    restored=next(item for item in store.get_matching(run)['calculation']['monthly']['employees'][0]['shifts']
        if item['movement_id']==2)
    assert restored['origin_location'] is None and restored['direct_transfer_override'] is False


def test_employee_default_applies_to_all_days_and_can_be_disabled(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1]['source_shifts'][0].update(start='18:00',end='23:00')
    extra=deepcopy(p['movements'][1]);extra.update(id=3,day='2026-08-02')
    first=deepcopy(p['movements'][0]);first.update(id=4,day='2026-08-02')
    p['movements'].extend((first,extra))
    with store.transaction() as db:
        db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    store.apply('itinerary_employee_default',{'run_id':run,'movement_id':2,
        'direct_transfer':True,'reason':'Altijd rechtstreeks'},store.snapshot()['revision'])
    shifts=store.get_matching(run)['calculation']['monthly']['employees'][0]['shifts']
    seconds=[item for item in shifts if item['movement_id'] in (2,3)]
    assert all(item['origin_location']=='LUCHTHAVEN' for item in seconds)
    assert all(item['direct_transfer_scope']=='EMPLOYEE' for item in seconds)
    assert all(item['direct_transfer_employee_default'] is True for item in seconds)
    store.apply('itinerary_transfer_override',{'run_id':run,'movement_id':2,
        'direct_transfer':False,'reason':'Alleen deze dag naar huis'},store.snapshot()['revision'])
    exception=store.get_matching(run)['calculation']['monthly']['employees'][0]['shifts']
    assert next(item for item in exception if item['movement_id']==2)['origin_location'] is None
    assert next(item for item in exception if item['movement_id']==2)['direct_transfer_employee_default'] is True
    assert next(item for item in exception if item['movement_id']==3)['origin_location']=='LUCHTHAVEN'
    store.apply('itinerary_employee_default',{'run_id':run,'movement_id':2,
        'direct_transfer':False,'reason':'Standaard verwijderen'},store.snapshot()['revision'])
    restored=store.get_matching(run)['calculation']['monthly']['employees'][0]['shifts']
    assert all(item['origin_location'] is None for item in restored if item['movement_id'] in (2,3))


def test_yasin_confirmed_default_is_seeded_once_on_existing_database(tmp_path):
    path=tmp_path/'routes.sqlite3';store=RouteStore(path)
    with store.transaction() as db:store.worker(db,'Kurt Yasin')
    RouteStore(path);RouteStore(path)
    with store.connect() as db:
        rows=db.execute('SELECT * FROM itinerary_employee_defaults').fetchall()
        assert len(rows)==1 and rows[0]['direct_transfer']==1


@pytest.mark.parametrize('start,end',[('11:00','17:00'),('08:00','09:00'),('13:00','13:00')])
def test_ambiguous_overlap_blocked_without_transfer_request(tmp_path,monkeypatch,start,end):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1]['source_shifts'][0].update(start=start,end=end)
    with store.transaction() as db:db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    assert not store.get_route_plan(run)['routes']
    assert all(r['amount'] is None for r in calculate(store,run,p)['rows'])


def test_bicycle_transfer_uses_cycling_profile(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    p['movements'][1]['routes']=[p['movements'][1]['routes'][1]]
    with store.transaction() as db:db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    transfer=next(r for r in store.get_route_plan(run)['routes'] if r['contexts'][0].get('route_kind')=='TRANSFER')
    assert transfer['profile']=='cycling'


def test_telework_is_not_a_physical_stop_in_daily_itinerary(tmp_path,monkeypatch):
    store,run,p,wid=multi_case(tmp_path,monkeypatch)
    store.apply('shift_transport_choice',{'run_id':run,'movement_id':1,'mode':'TELEWORK','reason':'HR bevestigt telework'},store.snapshot()['revision'])
    prepared=store.get_route_plan(run)
    assert prepared['excluded']==2  # Telework plus the train option on the remaining movement.
    assert prepared['routes'] and all(not context.get('origin_location') for route in prepared['routes'] for context in route['contexts'])
    rows=store.get_matching(run)['calculation']['rows']
    assert rows[0]['status']=='EXCLUDED_TELEWORK' and rows[0]['amount'] is None
    assert rows[1]['origin_location'] is None and rows[1]['journey_kind'] is None
