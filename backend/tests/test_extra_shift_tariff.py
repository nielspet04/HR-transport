import pytest
from app.calculation import calculate_movement,validate_km_rate
from test_calculation import movement,tariff
from test_special_tariff import special_tariff
from test_cached_calculation import setup_case,calculate


def rate(value='0.4326',start='2026-02-01',id=1):
    return {'id':id,'valid_from':start,'rate_per_km':value,'source':'Test'}


@pytest.mark.parametrize('night',[True,False,None])
def test_48h_roundtrip_replaces_both_tables(night):
    m=movement('17.001');m.update(extra_shift_48h=True,phase5_special=True,early_late=night)
    result=calculate_movement(m,[tariff()],[special_tariff()],[rate()])
    assert result['tariff_kind']=='EXTRA48' and result['distance']=='18'
    assert result['reimbursed_kms']=='36' and result['amount']=='15.57'
    assert result['rate_per_km']=='0.4326' and result['distance_factor']==2


def test_dated_rates_missing_rate_and_precision():
    m=movement('10');m.update(extra_shift_48h=True,phase5_special=True,early_late=False)
    rates=[rate(),rate('0.5000','2026-09-01',2)]
    assert calculate_movement(m,[tariff()],[],rates)['amount']=='8.65'
    m['day']='2026-09-01'
    assert calculate_movement(m,[],[],rates)['amount']=='10.00'
    assert calculate_movement(m,[tariff()],[],[])['amount'] is None
    assert validate_km_rate('0,4326')=='0.4326'


@pytest.mark.parametrize('value',['NaN','Infinity','-1','0.43261',None,''])
def test_invalid_rate_rejected(value):
    with pytest.raises(ValueError):validate_km_rate(value)


def test_settings_and_hr_correction_recalculate_persist(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    p['movements'][0].update(early_late=True,extra_shift_48h=True,phase5_special=True)
    assert calculate(store,run,p)['rows'][0]['amount']=='15.57'
    store.apply('extra_shift_tariff',{'valid_from':'2026-02-01','rate_per_km':'0.5000','reason':'Correctie tarief'},store.snapshot()['revision'])
    assert calculate(store,run,p)['rows'][0]['amount']=='18.00'
    store.apply('route_distance_override',{'route_id':1,'worker_id':wid,'kms':10,'reason':'HR afstand'},store.snapshot()['revision'])
    result=calculate(store,run,p)['rows'][0]
    assert result['amount']=='10.00' and result['distance_source']=='HR'
    from app.configuration.routes import RouteStore
    reopened=RouteStore(store.path)
    assert len(reopened.snapshot()['extra_shift_tariffs'])==2
    assert calculate(reopened,run,p)['rows'][0]['amount']=='10.00'


def test_missing_route_and_multilocation_still_blocked(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch,cached=False)
    p['movements'][0].update(early_late=False,extra_shift_48h=True,phase5_special=True)
    assert calculate(store,run,p)['rows'][0]['amount'] is None
    p['movements'].append({**p['movements'][0],'id':2,'location':'Other','source_location':'Other'})
    assert all(r['status']=='LATER_PHASE' and r['amount'] is None for r in calculate(store,run,p)['rows'])
