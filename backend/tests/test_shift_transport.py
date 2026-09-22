import json
from app import routing
from test_cached_calculation import setup_case


def choose(store,run,movement,mode,reason='HR bevestigt vervoer voor deze shift'):
    store.apply('shift_transport_choice',{'run_id':run,'movement_id':movement,'mode':mode,'reason':reason},store.snapshot()['revision'])


def test_train_shift_can_be_bike_or_car_and_bike_ignores_early_late(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    # Make the persisted shift early and normally train-only.
    p['movements'][0].update(routes=[{'route_id':99,'mode':'Trein','kms':None,'valid_from':'2026-01-01'}],
                             early_late=True,phase5_special=True,extra_shift_48h=False)
    with store.transaction() as db:db.execute('UPDATE matching_runs SET payload=? WHERE id=?',(json.dumps(p),run))
    assert store.get_matching(run)['calculation']['rows'][0]['status']=='EXCLUDED_TRAIN'

    choose(store,run,1,'BIKE')
    plan=store.get_route_plan(run);route=next(r for r in plan['routes'] if r['profile']=='cycling')
    monkeypatch.setattr(routing,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(routing,'request_distance',lambda *a:{'meters':'12001','kms':'12.001','alternatives_count':1})
    store.apply('route_distance_request',{'run_id':run,'cache_key':route['cache_key'],'consent':True},store.snapshot()['revision'])
    store.apply('bicycle_tariff',{'valid_from':'2026-02-01','rate_per_km':'0.36','reason':'HR bevestigt testtarief'},store.snapshot()['revision'])
    row=store.get_matching(run)['calculation']['rows'][0]
    assert row['status']=='CALCULATED' and row['tariff_kind']=='BICYCLE'
    assert row['distance']=='13' and row['reimbursed_kms']=='26' and row['amount']=='9.36'
    assert 'geen vroeg/laat' in row['reason'] and row['selected_mode']=='Fiets'

    choose(store,run,1,'AUTO')
    row=store.get_matching(run)['calculation']['rows'][0]
    assert row['selected_mode']=='Auto' and row['tariff_kind']=='SPECIAL'
    choose(store,run,1,'TRAIN')
    assert store.get_matching(run)['calculation']['rows'][0]['status']=='EXCLUDED_TRAIN'


def test_invalid_shift_transport_choice_rejected(tmp_path,monkeypatch):
    store,run,p,wid=setup_case(tmp_path,monkeypatch)
    import pytest
    with pytest.raises(ValueError):choose(store,run,1,'SCOOTER')
    with pytest.raises(ValueError):choose(store,run,999,'BIKE')
