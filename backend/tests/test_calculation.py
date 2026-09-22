"""Fictional phase-5 cases: no guessed amounts or transport fallbacks."""
import base64
from datetime import date,time
from decimal import Decimal
import pytest

from app.calculation import calculate_movement,pdf_start_tariff,validate_tariff
from app.configuration.routes import RouteStore
from app.matching import match_import
from app.importers.planet import HEADERS
from test_matching import config,RULES
from test_planet_cleaning import shift,imported
from test_planet_importer import write_xlsx


def tariff(id=1,start='2026-02-01'):
    return {'id':id,'valid_from':start,'source':'Test PDF','data':pdf_start_tariff()}


def movement(kms='17',day='2026-08-01'):
    return {'id':1,'day':day,'status':'MATCHED','phase5_special':False,
        'routes':[{'route_id':1,'mode':'Privé auto','kms':kms,'valid_from':'2026-02-01'}]}


@pytest.mark.parametrize('kms,amount',[('1','3.43'),('3','3.43'),('17','7.11'),('30','10.48'),
    ('31','10.81'),('33','10.81'),('34','11.49'),('39','12.19'),('60','15.96'),('61','16.27'),('68','18.44'),('100','28.36')])
def test_pdf_standard_table_and_long_distances(kms,amount):
    result=calculate_movement(movement(kms),[tariff()])
    assert result['amount']==amount and result['status']=='CALCULATED'
    assert result['route_id']==1 and result['tariff_id']==1
    assert result['distance_valid_from']=='2026-02-01'


def test_effective_date_and_same_date_corrections():
    new=tariff(2,'2026-09-01');new['data']['bands'][16]['amount']='8.00'
    assert calculate_movement(movement(day='2026-08-31'),[tariff(),new])['amount']=='7.11'
    assert calculate_movement(movement(day='2026-09-01'),[tariff(),new])['amount']=='8.00'
    assert calculate_movement(movement(day='2026-01-31'),[tariff()])['amount'] is None
    correction=tariff(3,'2026-09-01');correction['data']['bands'][16]['amount']='9.00'
    assert calculate_movement(movement(day='2026-09-01'),[new,correction])['tariff_id']==3


@pytest.mark.parametrize('kms',[None,'','n.v.t.','0','NaN','Infinity','-1'])
def test_unknown_invalid_or_fractional_distance_never_zero_or_guessed(kms):
    result=calculate_movement(movement(kms),[tariff()])
    assert result['status']=='BLOCKED' and result['amount'] is None


@pytest.mark.parametrize('kms,rounded',[('17.01','18'),('17.00','17'),('60.01','61'),('0.01','1')])
def test_confirmed_ceiling_rule(kms,rounded):
    result=calculate_movement(movement(kms),[tariff()])
    assert result['status']=='CALCULATED' and result['distance']==rounded


def test_bike_alternative_does_not_duplicate_car_amount_and_company_car_not_private():
    m=movement();m['routes'].append({'route_id':2,'mode':'Fiets','kms':'10','valid_from':'2026-02-01'})
    assert calculate_movement(m,[tariff()])['amount']=='7.11'
    m['routes'][0]['mode']='Dienstwagen'
    result=calculate_movement(m,[tariff()]);assert result['status']=='EXCLUDED_COMPANY_CAR' and result['amount'] is None


def test_ambiguous_cars_train_and_unmatched():
    m=movement();m['routes'].append({**m['routes'][0],'mode':'Auto','route_id':2})
    assert calculate_movement(m,[tariff()])['amount'] is None
    m['routes']= [{'route_id':1,'mode':'Trein','kms':None,'valid_from':'2026-02-01'}]
    result=calculate_movement(m,[tariff()]);assert result['status']=='EXCLUDED_TRAIN' and result['amount'] is None
    m['status']='UNMATCHED_LOCATION';assert calculate_movement(m,[tariff()])['status']=='BLOCKED'
    m=movement();m['routes'].append({'route_id':2,'mode':'Trein','kms':None,'valid_from':'2026-02-01'})
    assert calculate_movement(m,[tariff()])['status']=='BLOCKED'


@pytest.mark.parametrize('changes',[{'start_time':time(5,59)},
    {'start_time':time(22),'end_time':time(6)}, {'remark':'48h_ICTS_Extra_Shift'}])
def test_special_source_shift_blocks_whole_deduplicated_movement(changes):
    c=config();c['car_tariffs']=[tariff()]
    result=match_import(imported(shift(customer='TUI'),shift(3,customer='TUI',**changes)),c,RULES)
    assert len(result['movements'])==1
    row=result['calculation']['rows'][0]
    assert row['status']=='LATER_PHASE' and row['amount'] is None


def test_ordinary_boundaries_and_two_locations():
    c=config();c['car_tariffs']=[tariff()]
    c['routes'].append({'id':3,'worker_id':1,'mode':'Auto','location':'Other'})
    c['versions'].append({'id':3,'route_id':3,'kms':'17','valid_from':'2026-02-01'})
    result=match_import(imported(shift(customer='TUI',start_time=time(6),end_time=time(22)),shift(3,customer='Other')),c,RULES)
    rows=result['calculation']['rows'];assert len(rows)==2 and all(r['status']=='CALCULATED' for r in rows)
    assert not result['calculation']['payroll_ready']


@pytest.mark.parametrize('start,end,special',[
    (time(19),time(7),False),(time(19),time(5),False),
    (time(5),time(19),True),(time(21,59),time(5),False),
    (time(22),time(7),True),(time(23,59),time(7),True),
    (time(0),time(8),True),(time(5,59),time(19),True),
    (time(6),time(19),False)])
def test_only_start_determines_early_late_window(start,end,special):
    c=config();c['car_tariffs']=[tariff()]
    result=match_import(imported(shift(customer='TUI',start_time=start,end_time=end,
        end_time_day_offset=1 if end<start else None)),c,RULES)
    assert result['movements'][0]['phase5_special'] is special
    row=result['calculation']['rows'][0]
    assert row['status']==('LATER_PHASE' if special else 'CALCULATED')
    assert (row['amount'] is None)==special


def test_tariff_validation_no_gaps_overlap_infinite_or_negative_amounts():
    for field,value in [('extra_per_km','NaN'),('extra_per_km','-1')]:
        data=pdf_start_tariff();data[field]=value
        with pytest.raises(ValueError):validate_tariff(data)
    for change in ('gap','overlap','negative','fraction'):
        data=pdf_start_tariff()
        if change=='gap':data['bands'].pop(0)
        if change=='overlap':data['bands'][1]['from_km']=1
        if change=='negative':data['bands'][0]['amount']='-1'
        if change=='fraction':data['bands'][0]['amount']='1.001'
        with pytest.raises(ValueError):validate_tariff(data)


def upload_data(tmp_path,day='2026-09-01'):
    source=write_xlsx(tmp_path/'september.xlsx',[list(HEADERS),
        ['006','Voorbeeld','Alex',None,day,'Test','08:00','16:00',None,'TUI',999]],sheet_name='Total kms')
    return source,{'filename':source.name,'content':base64.b64encode(source.read_bytes()).decode()}


def test_upload_automatic_calculation_retained_private_source_and_tariff_versions(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Voorbeeld Alex','location':'LUCHTHAVEN','mode':'Auto','kms':'17',
        'valid_from':'2026-02-01','reason':'Test'},0)
    source,data=upload_data(tmp_path)
    store.apply('planet_upload',data,store.snapshot()['revision'])
    old=store.snapshot()['matching'];assert old['month']=='2026-09'
    assert old['calculation']['rows'][0]['amount']=='7.11'
    source.unlink()  # Refresh uses retained copy, not original Downloads file.
    new=pdf_start_tariff();new['bands'][16]['amount']='8.00'
    store.apply('car_tariff',{**new,'valid_from':'2026-09-01','reason':'Updated'},store.snapshot()['revision'])
    assert store.get_matching(old['run_id'])['stale']
    store.apply('matching_refresh',{'run_id':old['run_id']},store.snapshot()['revision'])
    current=store.snapshot()['matching'];assert current['calculation']['rows'][0]['amount']=='8.00'
    assert store.get_matching(old['run_id'])['calculation']['rows'][0]['amount']=='7.11'
    assert len(store.snapshot()['car_tariffs'])==2
    assert RouteStore(store.path).snapshot()['matching']['calculation']==current['calculation']


def test_bad_upload_and_stale_revision_leave_database_and_sources_unchanged(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3');before=store.snapshot()
    with pytest.raises(ValueError):store.apply('planet_upload',{'filename':'bad.xlsx','content':base64.b64encode(b'bad').decode()},0)
    assert store.snapshot()==before
    source,data=upload_data(tmp_path)
    with pytest.raises(ValueError):store.apply('planet_upload',data,99)
    assert store.snapshot()==before
    assert not list((tmp_path/'planet_uploads').glob('*.xlsx'))


def test_new_upload_agent_stays_visible_and_is_never_paid_without_match(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3');source,data=upload_data(tmp_path)
    store.apply('planet_upload',data,0)
    result=store.snapshot()['matching']
    assert result['agents'][0]['planet_id']=='006'
    assert result['calculation']['rows'][0]['status']=='BLOCKED'
    assert result['calculation']['rows'][0]['amount'] is None


def test_upload_http_and_tariff_configuration(tmp_path):
    import http.client,json,threading
    from app.configuration.server import make_server
    store=RouteStore(tmp_path/'routes.sqlite3');server=make_server(store,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request('GET','/api/state');response=client.getresponse();state=json.loads(response.read())
        _,data=upload_data(tmp_path)
        headers={'Content-Type':'application/json','X-CSRF-Token':state['csrf']}
        client.request('POST','/api/action/planet_upload',json.dumps({'revision':state['revision'],'data':data}),headers)
        response=client.getresponse();assert response.status==200;response.read()
        result=store.snapshot();assert result['matching']['month']=='2026-09'
        tariff_data={**pdf_start_tariff(),'valid_from':'2026-09-01','reason':'HTTP test'}
        client.request('POST','/api/action/car_tariff',json.dumps({'revision':result['revision'],'data':tariff_data}),headers)
        response=client.getresponse();assert response.status==200;response.read()
        assert len(store.snapshot()['car_tariffs'])==2
    finally:
        client.close();server.shutdown();server.server_close();thread.join(timeout=5)


def test_tariff_change_is_atomic_and_same_date_preserves_old_record(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3');data=pdf_start_tariff()
    store.apply('car_tariff',{**data,'valid_from':'2026-02-01','reason':'Correction'},0)
    before=store.snapshot();assert len(before['car_tariffs'])==2
    data['bands'][0]['amount']='NaN'
    with pytest.raises(ValueError):store.apply('car_tariff',{**data,'valid_from':'2026-09-01','reason':'Bad'},before['revision'])
    assert store.snapshot()==before
