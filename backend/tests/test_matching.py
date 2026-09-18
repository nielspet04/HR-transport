"""Phase 4 acceptance: normalization, ambiguity, month scope, no trip fan-out."""
from dataclasses import replace
from datetime import date
from pathlib import Path
import json
import os
import pytest
from app.matching import match_import
from app.configuration.routes import RouteStore
from app.importers.planet import import_planet,HEADERS
from test_planet_cleaning import shift,imported
from test_planet_importer import write_xlsx

RULES=Path(__file__).resolve().parents[2]/'config/locations.toml'


def config():
    return {'workers':[{'id':1,'name':'Voorbeeld Alex'}],
        'routes':[{'id':1,'worker_id':1,'location':'LUCHTHAVEN','mode':'Fiets'},
                  {'id':2,'worker_id':1,'location':'LUCHTHAVEN','mode':'Privé auto'}],
        'versions':[{'id':1,'route_id':1,'valid_from':'2026-02-01','kms':'10'},
                    {'id':2,'route_id':2,'valid_from':'2026-02-01','kms':'15'}],
        'employee_links':[],'location_links':[]}


def test_case_spaces_split_names_and_multiple_routes_do_not_duplicate():
    result=match_import(imported(shift(last_name='  VOORBEELD ',first_name=' Alex  ',customer='TUI'),shift(3,customer='DELTA AIRLINES')),config(),RULES)
    assert result['summary']['movements']==1 and result['summary']['source_shifts']==2
    movement=result['movements'][0]
    assert movement['status']=='MATCHED' and len(movement['routes'])==2
    assert movement['source_shifts'][0].keys()=={'row','customer','task','start','end','end_day_offset'}


def test_normalized_location_and_different_name_order():
    c=config();c['routes'][0]['location']='Postnl  Test';c['routes'][1]['location']='Other'
    c['workers'][0]['name']='Alex Voorbeeld'
    result=match_import(imported(shift(customer=' POSTNL Test ')),c,RULES)
    assert result['movements'][0]['status']=='MATCHED'


def test_fuzzy_is_only_suggestion_never_automatic():
    result=match_import(imported(shift(last_name='Voorbeelt',customer='TUI')),config(),RULES)
    agent=result['agents'][0]
    assert agent['status']=='UNMATCHED_EMPLOYEE' and agent['worker_id'] is None
    assert agent['suggestions'][0]['worker_id']==1
    assert result['movements'][0]['routes']==[]


def test_missing_location_and_missing_employee_location_are_distinct():
    unknown=match_import(imported(shift(customer='Other site')),config(),RULES)
    assert unknown['movements'][0]['status']=='UNMATCHED_LOCATION'
    c=config();c['workers'].append({'id':2,'name':'Other Agent'})
    missing=match_import(imported(shift(last_name='Other',first_name='Agent',customer='TUI')),c,RULES)
    assert missing['movements'][0]['status']=='UNMATCHED_EMPLOYEE_LOCATION'


def test_collision_and_changed_name_guard_are_ambiguous():
    c=config();c['workers'].append({'id':2,'name':' VOORBEELD   ALEX '})
    assert match_import(imported(shift(customer='TUI')),c,RULES)['agents'][0]['status']=='AMBIGUOUS'
    c=config();c['employee_links']=[{'planet_id':'006','worker_id':1,'source_keys':json.dumps(['old name'])}]
    assert match_import(imported(shift(customer='TUI')),c,RULES)['agents'][0]['status']=='AMBIGUOUS'


def test_two_ids_do_not_silently_become_one_worker():
    data=imported(shift(customer='TUI'),shift(3,employee_id='007',customer='TUI'))
    assert all(a['status']=='AMBIGUOUS' for a in match_import(data,config(),RULES)['agents'])
    c=config();c['employee_links']=[{'planet_id':pid,'worker_id':1,'source_keys':json.dumps(['voorbeeld alex'])} for pid in ('006','007')]
    assert all(a['status']=='MATCHED' for a in match_import(data,c,RULES)['agents'])


def test_conflicting_names_same_id_not_first_wins():
    result=match_import(imported(shift(customer='TUI'),shift(3,last_name='Different',customer='TUI')),config(),RULES)
    assert result['agents'][0]['status']=='AMBIGUOUS'


def test_versions_selected_by_shift_date_no_future_fallback():
    c=config();c['versions'].append({'id':3,'route_id':1,'valid_from':'2026-09-01','kms':'20'})
    aug=match_import(imported(shift(customer='TUI')),c,RULES)
    assert aug['movements'][0]['routes'][0]['kms']=='10'
    jan=match_import(imported(shift(day=date(2026,1,2),customer='TUI'),month='2026-01'),c,RULES)
    assert jan['movements'][0]['routes']==[] and jan['movements'][0]['route_status']=='NO_EFFECTIVE_ROUTE'


def test_train_distance_not_applicable_even_with_old_numeric_distance():
    c=config();c['routes'][0]['mode']=' Trein '
    c['versions'][0]['kms']='42'
    result=match_import(imported(shift(customer='TUI')),c,RULES)
    route=result['movements'][0]['routes'][0]
    assert route['kms'] is None and route['km_applicable'] is False
    assert result['movements'][0]['status']=='MATCHED'


def test_train_add_update_and_move_without_distance(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Test Agent','location':'Test','mode':'Trein',
        'valid_from':'2026-02-01','reason':'Test'},0)
    route=store.snapshot()['routes'][0]
    store.apply('route_update',{'route_id':route['id'],'kms':'n.v.t.',
        'valid_from':'2026-03-01','reason':'Test'},store.snapshot()['revision'])
    store.apply('worker_move',{'worker_id':route['worker_id'],
        'updates':[{'route_id':route['id']}],'valid_from':'2026-04-01','reason':'Move'},store.snapshot()['revision'])
    assert all(v['kms'] is None for v in store.snapshot()['versions'])
    with pytest.raises(ValueError):store.apply('route_add',{'name':'Test Agent','location':'Test','mode':'Fiets',
        'valid_from':'2026-02-01','reason':'Test'},store.snapshot()['revision'])


def test_confirmed_location_changes_cleaning_not_just_match_label():
    c=config();c['location_links']=[{'customer':'new airport customer','location':'LUCHTHAVEN'}]
    result=match_import(imported(shift(customer='TUI'),shift(3,customer='New Airport Customer')),c,RULES)
    assert result['summary']['movements']==1 and result['summary']['duplicates']==1
    c['location_links']=[{'customer':'tui','location':'Other'}]
    with pytest.raises(ValueError):match_import(imported(shift(customer='TUI')),c,RULES)


def test_explicit_month_and_accounting():
    with pytest.raises(ValueError):match_import(imported(shift(),month=None),config(),RULES)
    data=imported(shift(customer='TUI'),shift(3,employee_id='1112'),shift(4,remark='Telework'))
    report=match_import(data,config(),RULES)['summary']
    assert report['input_rows']==report['movements']+report['duplicates']+report['ghosts']+report['telework']


def fake_planet(tmp_path):
    rows=[list(HEADERS),['006','Voorbeelt','Alex',None,'2026-08-01','Test','08:00','16:00',None,'New Site',999]]
    return write_xlsx(tmp_path/'planet.xlsx',rows,sheet_name='Total kms')


def prepared_store(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Voorbeeld Alex','location':'LUCHTHAVEN','mode':'Fiets','kms':'10','valid_from':'2026-02-01','reason':'Test'},0)
    source=fake_planet(tmp_path);snapshot=store.snapshot();payload=match_import(import_planet(source,month='2026-08'),snapshot,RULES)
    run=store.save_matching(payload,source,snapshot['revision'])
    return store,source,run


def test_persistent_confirmations_rerun_and_old_snapshot_stale(tmp_path):
    store,source,run=prepared_store(tmp_path)
    store.apply('matching_employee',{'run_id':run,'planet_id':'006','worker_id':1,'reason':'HR bevestigt'},store.snapshot()['revision'])
    assert store.snapshot()['matching']['agents'][0]['status']=='MATCHED'
    new=store.snapshot()['matching']['run_id']
    store.apply('matching_location',{'run_id':new,'customer':'New Site','location':'LUCHTHAVEN','reason':'HR locatie'},store.snapshot()['revision'])
    current=store.snapshot()['matching'];assert current['movements'][0]['status']=='MATCHED' and not current['stale']
    assert store.get_matching(run)['stale']
    assert RouteStore(store.path).snapshot()['employee_links'][0]['worker_id']==1


def test_missing_source_confirmation_rolls_back(tmp_path):
    store,source,run=prepared_store(tmp_path)
    source.rename(tmp_path/'moved.xlsx');before=store.snapshot()
    with pytest.raises(ValueError):store.apply('matching_employee',{'run_id':run,'planet_id':'006','worker_id':1,'reason':'HR'},before['revision'])
    assert store.snapshot()==before


def test_refresh_processes_all_months_and_keeps_unmatched_agents(tmp_path):
    store,source,run=prepared_store(tmp_path)
    write_xlsx(source,[list(HEADERS),
        ['006','Voorbeelt','Alex',None,'2026-08-01','Test','08:00','16:00',None,'New Site',999],
        ['007','New','Agent',None,'2026-07-01','Test','22:00','06:00',None,'TUI',999]],sheet_name='Total kms')
    store.apply('matching_refresh',{'run_id':run},store.snapshot()['revision'])
    latest={}
    for r in store.snapshot()['matching_runs']:latest.setdefault(r['month'],r['id'])
    assert set(latest)=={'2026-07','2026-08'}
    july=store.get_matching(latest['2026-07'])
    assert july['agents'][0]['planet_id']=='007'
    assert july['agents'][0]['status']=='UNMATCHED_EMPLOYEE'
    assert july['summary']['movements']==1
    before=store.snapshot();source.rename(tmp_path/'missing.xlsx')
    with pytest.raises(ValueError):store.apply('matching_refresh',{'run_id':run},before['revision'])
    assert store.snapshot()==before


def test_confirmation_updates_all_source_months(tmp_path):
    store,source,run=prepared_store(tmp_path)
    write_xlsx(source,[list(HEADERS)]+[
        ['006','Voorbeelt','Alex',None,f'2026-{month}-01','Test','08:00','16:00',None,'New Site',999]
        for month in ('07','08')],sheet_name='Total kms')
    runs=store.process_source(source,store.snapshot()['revision'])
    august=next(r['run_id'] for r in runs if r['month']=='2026-08')
    store.apply('matching_employee',{'run_id':august,'planet_id':'006','worker_id':1,'reason':'HR'},store.snapshot()['revision'])
    for row in store.snapshot()['matching_runs'][:2]:
        assert store.get_matching(row['id'])['agents'][0]['status']=='MATCHED'


@pytest.mark.skipif(not os.environ.get('PLANET_SOURCE'),reason='Private optional August acceptance')
def test_private_august_unchanged_cleaning_counts(tmp_path):
    result=match_import(import_planet(os.environ['PLANET_SOURCE'],month='2026-08'),config(),RULES)
    assert result['summary']['movements']==964 and result['summary']['source_shifts']==1288
    assert result['summary']['input_rows']==1406
