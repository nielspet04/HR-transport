from datetime import time
from copy import deepcopy
import pytest
from app.calculation import calculate_movement,pdf_special_tariff
from app.matching import match_import
from test_calculation import movement,tariff
from test_matching import config,RULES
from test_planet_cleaning import shift,imported
from test_cached_calculation import setup_case,calculate


def special_tariff(start='2026-02-01'):
    return {'id':9,'valid_from':start,'source':'PDF 150%-kolom','data':pdf_special_tariff()}


@pytest.mark.parametrize('start,end,special',[(time(19),time(7),False),(time(19),time(5),False),(time(21,59),time(7),False),(time(22),time(6),True),(time(5,59),time(19),True),(time(6),time(14),False),(time(0),time(8),True)])
def test_only_shift_start_selects_exact_table(start,end,special):
    c=config()
    p=match_import(imported(shift(customer='TUI',start_time=start,end_time=end,end_time_day_offset=1 if end<start else None)),c,RULES)
    m=movement('18');m.update(phase5_special=p['movements'][0]['phase5_special'],early_late=p['movements'][0]['early_late'],extra_shift_48h=False)
    result=calculate_movement(m,[tariff()],[special_tariff()])
    assert result['amount']==('9.22' if special else '7.38')
    assert result['tariff_kind']==('SPECIAL' if special else 'STANDARD')


@pytest.mark.parametrize('km,amount',[('1','4.29'),('6','5.37'),('10','6.66'),('17','8.89'),('30','13.09'),('31','13.51'),('58','19.96'),('60','19.96'),('61','20.27'),('68','22.44'),('17.01','9.22')])
def test_pdf_special_amounts_and_long_distance(km,amount):
    m=movement(km);m.update(phase5_special=True,early_late=True,extra_shift_48h=False)
    assert calculate_movement(m,[tariff()],[special_tariff()])['amount']==amount


def test_missing_special_tariff_never_standard_fallback_and_48h_separate():
    m=movement('18');m.update(phase5_special=True,early_late=True,extra_shift_48h=False)
    assert calculate_movement(m,[tariff()],[])['amount'] is None
    assert calculate_movement(m,[tariff()],[special_tariff('2026-09-01')])['amount'] is None
    m['extra_shift_48h']=True
    assert calculate_movement(m,[tariff()],[special_tariff()])['status']=='LATER_PHASE'


def test_cache_and_hr_correction_apply_special_table(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    p['movements'][0].update(early_late=True,extra_shift_48h=False,phase5_special=True)
    result=calculate(store,run,p)['rows'][0]
    assert result['distance']=='18' and result['amount']=='9.22' and result['distance_source']=='Mapbox'
    store.apply('route_distance_override',{'route_id':1,'worker_id':wid,'kms':10,'reason':'Controle'},store.snapshot()['revision'])
    result=calculate(store,run,p)['rows'][0]
    assert result['distance']=='10' and result['amount']=='6.66' and result['distance_source']=='HR'


def test_special_settings_dated_and_standard_unchanged(tmp_path):
    from app.configuration.routes import RouteStore
    store=RouteStore(tmp_path/'test.sqlite3');before=deepcopy(store.snapshot()['car_tariffs'])
    data={**pdf_special_tariff(),'valid_from':'2026-09-01','reason':'Nieuw speciaal tarief'}
    data['bands'][17]['amount']='10.00'
    store.apply('special_car_tariff',data,store.snapshot()['revision'])
    tariffs=store.snapshot()['special_car_tariffs']
    m=movement('18');m.update(phase5_special=True,early_late=True,extra_shift_48h=False)
    assert calculate_movement(m,[tariff()],tariffs)['amount']=='9.22'
    m['day']='2026-09-01'
    assert calculate_movement(m,[tariff()],tariffs)['amount']=='10.00'
    assert store.snapshot()['car_tariffs']==before
