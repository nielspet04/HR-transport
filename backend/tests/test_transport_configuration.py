"""Persistent/versioned config, relocation rollback and local HTTP safeguards."""
import http.client
import json
from pathlib import Path
import threading

import pytest
from app.configuration.store import Store
from app.configuration.server import make_server
from app.cleaning import CleaningPolicy,clean_import
from app.importers.reference import import_reference
from test_reference_importer import make
from test_planet_cleaning import shift,imported


def apply(store,action,**data):
    store.apply(action,data,store.snapshot()['revision'])


def setup(store):
    apply(store,'employee',name='Voorbeeld Alex')
    apply(store,'location',name='LUCHTHAVEN')
    apply(store,'location',name='POSTNL TEST')
    apply(store,'setting',employee_id=1,location_id=1,kms='10',mode='TRAIN',valid_from='2026-01-01',reason='Start')
    apply(store,'setting',employee_id=1,location_id=2,kms='20',mode='PRIVATE_CAR',valid_from='2026-01-01',reason='Start')


def test_persisted_different_modes_and_relocation_preserves_history(tmp_path):
    path=tmp_path/'state.sqlite3';s=Store(path);setup(s)
    apply(s,'relocation',employee_id=1,valid_from='2026-09-15',reason='Verhuizing',updates=[
        {'location_id':1,'kms':'30,5','mode':'TRAIN'},
        {'location_id':2,'kms':'40','mode':'BIKE'}])
    reopened=Store(path)
    assert reopened.resolve(1,1,'2026-09-14')['kms']=='10'
    assert reopened.resolve(1,1,'2026-09-15')['kms']=='30.5'
    assert reopened.resolve(1,2,'2026-09-15')['mode']=='BIKE'
    assert reopened.resolve(1,1,'2025-12-31') is None
    assert reopened.resolve(999,1,'2026-09-15') is None
    assert len(reopened.snapshot()['settings'])==4


@pytest.mark.parametrize('updates',[
    [{'location_id':1,'kms':'30','mode':'TRAIN'}],
    [{'location_id':1,'kms':'30','mode':'TRAIN'},{'location_id':2,'kms':'-1','mode':'BIKE'}],
    [{'location_id':1,'kms':'30','mode':'TRAIN'},{'location_id':1,'kms':'40','mode':'BIKE'}],
])
def test_relocation_all_or_nothing_and_all_locations_required(tmp_path,updates):
    s=Store(tmp_path/'state.sqlite3');setup(s);before=s.snapshot()
    with pytest.raises(ValueError):apply(s,'relocation',employee_id=1,valid_from='2026-09-15',reason='Move',updates=updates)
    assert s.snapshot()==before


def test_same_date_backdating_and_stale_revision_refused(tmp_path):
    s=Store(tmp_path/'state.sqlite3');setup(s)
    for day in ('2026-01-01','2025-12-01'):
        with pytest.raises(ValueError):apply(s,'setting',employee_id=1,location_id=1,kms='99',mode='BIKE',valid_from=day,reason='Change')
    with pytest.raises(ValueError):s.apply('employee',{'name':'Other'},0)
    assert s.resolve(1,1,'2026-09-15')['kms']=='10'


@pytest.mark.parametrize('kms', ['NaN','Infinity','-3','',True])
def test_invalid_distance_no_write(tmp_path,kms):
    s=Store(tmp_path/'state.sqlite3');setup(s);before=s.snapshot()
    with pytest.raises(ValueError):apply(s,'setting',employee_id=1,location_id=1,kms=kms,mode='BIKE',valid_from='2026-02-01',reason='Change')
    assert s.snapshot()==before


def test_once_bootstrap_never_overwrites_manual_config(tmp_path):
    s=Store(tmp_path/'state.sqlite3');setup(s)
    r=import_reference(make(tmp_path,[['Voorbeeld Alex','APT',99,'Fiets']]))
    assert s.seed_reference(r)==1 and s.seed_reference(r)==0
    assert s.resolve(1,1,'2026-09-15')['kms']=='10'
    apply(s,'candidate',candidate_id=1,employee_id=1,location_id=1,kms='99',mode='BIKE',valid_from='2026-10-01',reason='Reference reviewed')
    assert s.resolve(1,1,'2026-09-15')['kms']=='10'
    assert s.resolve(1,1,'2026-10-01')['kms']=='99'
    with pytest.raises(ValueError):apply(s,'candidate',candidate_id=1,employee_id=1,location_id=1,kms='99',mode='BIKE',valid_from='2026-11-01',reason='Again')


def test_bulk_reference_creates_workers_locations_and_confirmed_settings(tmp_path):
    s=Store(tmp_path/'state.sqlite3');s.bootstrap_locations([])
    result=import_reference(make(tmp_path,[
        ['Alex Test','APT',12,'Trein'],[' Alex Test ','apt',12,'Trein'],
        ['Alex Test','PostNL Test',25,'Fiets'],['New Test','Wework',8,'Privé auto']]))
    s.seed_reference(result)
    report=s.confirm_reference('2026-02-01')
    assert report=={'employees_created':2,'settings_created':3,'rows_confirmed':4,'rows_pending':0}
    assert len(s.snapshot()['employees'])==2
    assert s.resolve(1,1,'2026-08-01')['kms']=='12'
    assert s.resolve(1,1,'2026-01-31') is None
    again=s.confirm_reference('2026-02-01')
    assert again['settings_created']==again['employees_created']==0
    apply(s,'setting',employee_id=1,location_id=1,kms='30',mode='TRAIN',valid_from='2026-09-01',reason='Move')
    s.confirm_reference('2026-02-01')
    assert s.resolve(1,1,'2026-09-17')['kms']=='30'


def test_bulk_reference_does_not_pick_conflict_after_location_aliasing(tmp_path):
    s=Store(tmp_path/'state.sqlite3');s.bootstrap_locations([])
    apply(s,'alias',source='reference',name='Airport',location_id=1)
    s.seed_reference(import_reference(make(tmp_path,[
        ['Alex','APT',12,'Trein'],['Alex','Airport',13,'Trein'],
        ['Other','PostNL',None,'Fiets'],['Other','Wework',9,'auto']])))
    counts=s.confirm_reference('2026-02-01')
    assert counts['employees_created']==2 and counts['rows_pending']==4
    assert not s.snapshot()['settings']


def test_bulk_reference_never_overwrites_existing_manual_settings(tmp_path):
    s=Store(tmp_path/'state.sqlite3');setup(s);s.bootstrap_locations([])
    s.seed_reference(import_reference(make(tmp_path,[['Voorbeeld Alex','APT',99,'Fiets']])))
    counts=s.confirm_reference('2026-02-01')
    assert counts['employees_created']==counts['settings_created']==0
    assert counts['rows_pending']==1
    assert s.resolve(1,1,'2026-08-01')['kms']=='10'


def test_new_planet_agent_requires_explicit_binding_and_setting(tmp_path):
    s=Store(tmp_path/'state.sqlite3');s.register_planet(clean_import(imported(shift(employee_id='TEST-NEW'))))
    assert s.snapshot()['planet_agents'][0]['employee_id'] is None
    apply(s,'employee',name='Voorbeeld Alex')
    apply(s,'link',planet_id='TEST-NEW',employee_id=1)
    assert Store(s.path).snapshot()['planet_agents'][0]['employee_id']==1
    assert s.resolve(1,1,'2026-09-15') is None
    with pytest.raises(ValueError):apply(s,'link',planet_id='TEST-NEW',employee_id=1)


def test_alias_persists_and_drives_cleaning_and_apt_is_confirmed(tmp_path):
    from app.cleaning.locations import load_location_rules
    _,rules=load_location_rules(Path(__file__).resolve().parents[2]/'config/locations.toml')
    s=Store(tmp_path/'state.sqlite3');s.bootstrap_locations(rules)
    assert any(a['source']=='reference' and a['name_key']=='apt' for a in s.snapshot()['aliases'])
    apply(s,'alias',source='planet',name='NEW CUSTOMER',location_id=1)
    policy=Store(s.path).cleaning_policy(CleaningPolicy())
    c=clean_import(imported(shift(customer='TUI'),shift(3,customer='NEW CUSTOMER')),policy=policy)
    assert c.report.remaining_movements==1


def test_backup_survives_and_no_overwrite(tmp_path):
    s=Store(tmp_path/'state.sqlite3');setup(s);target=tmp_path/'backup.sqlite3'
    s.backup(target)
    assert Store(target).snapshot()==s.snapshot()
    with pytest.raises(ValueError):s.backup(target)


def test_ignore_candidate_persists_is_reversible_and_never_changes_settings(tmp_path):
    s=Store(tmp_path/'state.sqlite3');setup(s)
    s.seed_reference(import_reference(make(tmp_path,[['Voorbeeld Alex','APT',None,'Trein']])))
    original=s.snapshot()['settings']
    apply(s,'ignore_candidate',candidate_id=1,reason='Overbodig')
    reopened=Store(s.path)
    assert reopened.snapshot()['candidates'][0]['reviewed']==2
    assert reopened.snapshot()['settings']==original
    reopened.confirm_reference('2026-02-01')
    assert reopened.snapshot()['candidates'][0]['reviewed']==2
    assert reopened.snapshot()['changes'][-1]['reason']=='Overbodig'
    with pytest.raises(ValueError):apply(s,'ignore_candidate',candidate_id=1,reason='Again')
    with pytest.raises(ValueError):apply(s,'candidate',candidate_id=1,employee_id=1,location_id=1,kms='3',mode='BIKE',valid_from='2026-10-01',reason='No')
    apply(s,'restore_candidate',candidate_id=1)
    assert s.snapshot()['candidates'][0]['reviewed']==0
    assert s.snapshot()['settings']==original


@pytest.mark.parametrize('candidate,reason',[(999,'Overbodig'),(True,'Overbodig'),(1,''),(1,' '*3)])
def test_ignore_invalid_or_missing_reason_rolls_back(tmp_path,candidate,reason):
    s=Store(tmp_path/'state.sqlite3')
    s.seed_reference(import_reference(make(tmp_path,[['Alex','APT',None,'Trein']])))
    before=s.snapshot()
    with pytest.raises(ValueError):apply(s,'ignore_candidate',candidate_id=candidate,reason=reason)
    assert s.snapshot()==before


def test_confirmed_candidate_cannot_be_ignored(tmp_path):
    s=Store(tmp_path/'state.sqlite3');s.bootstrap_locations([])
    s.seed_reference(import_reference(make(tmp_path,[['Alex','APT',12,'Trein']])))
    s.confirm_reference('2026-02-01');before=s.snapshot()
    with pytest.raises(ValueError):apply(s,'ignore_candidate',candidate_id=1,reason='Overbodig')
    assert s.snapshot()==before


def test_http_security_and_create_flow(tmp_path):
    s=Store(tmp_path/'state.sqlite3');server=make_server(s,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request('GET','/api/state');response=client.getresponse();state=json.loads(response.read());assert response.status==200
        payload=json.dumps({'revision':state['revision'],'data':{'name':'Voorbeeld Alex'}})
        client.request('POST','/api/action/employee',payload,{'Content-Type':'application/json'})
        response=client.getresponse();response.read();assert response.status==403
        client.request('POST','/api/action/employee',payload,{'Content-Type':'application/json','X-CSRF-Token':state['csrf'],'Origin':'https://evil.example'})
        response=client.getresponse();response.read();assert response.status==403
        client.request('POST','/api/action/employee',payload,{'Content-Type':'application/json','X-CSRF-Token':state['csrf']})
        response=client.getresponse();response.read();assert response.status==200
        assert s.snapshot()['employees'][0]['name']=='Voorbeeld Alex'
        client.request('GET','/',headers={'Host':'evil.example'})
        response=client.getresponse();response.read();assert response.status==403
        for path in ('/','/app.js','/style.css'):
            client.request('GET',path);response=client.getresponse();assert response.status==200;response.read()
    finally:
        client.close();server.shutdown();server.server_close();thread.join(timeout=5)
