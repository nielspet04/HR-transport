import json
import pytest
from app.configuration.routes import RouteStore
from app.configuration.addresses import append_address, import_addresses


def test_country_confirmation_is_dated_safe_and_repeatable(tmp_path):
    from app.configuration.addresses import confirm_belgium
    store, worker = setup_store(tmp_path)
    with store.transaction() as db:
        append_address(db, worker, '2026-01-01', address(), 'Import')
        other = store.worker(db, 'Ander Voorbeeld')
        append_address(db, other, '2026-01-01', {**address(), 'country': 'NL'}, 'Handmatig')
    report = confirm_belgium(store, store.snapshot()['revision'])
    assert report == {'profiles': 1, 'candidates': 0}
    versions = [a for a in store.snapshot()['addresses'] if a['worker_id'] == worker]
    assert [a['address']['country'] for a in versions] == ['', 'BE']
    assert all(a['valid_from'] == '2026-01-01' for a in versions)
    assert confirm_belgium(store, store.snapshot()['revision'])['profiles'] == 0
    assert len(store.snapshot()['addresses']) == 3
    assert next(a for a in store.snapshot()['addresses'] if a['worker_id'] == other)['address']['country'] == 'NL'


def setup_store(tmp_path):
    store = RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        worker = store.worker(db, 'Voorbeeld Alex')
    return store, worker


def address():
    return {'street':'Teststraat','number':'12','unit':'','postal_code':'1000','city':'Brussel','country':''}


def test_import_existing_profiles_and_idempotence(tmp_path, monkeypatch):
    store, worker = setup_store(tmp_path)
    monkeypatch.setattr('app.configuration.addresses.read_addresses', lambda source: ('abc',[
        {'row':2,'name':'  VOORBEELD   alex ','address':address()},
        {'row':3,'name':'Onbekend Persoon','address':address()}]))
    report = import_addresses(store, 'unused', '2026-01-01', store.snapshot()['revision'])
    assert report['linked'] == report['review'] == 1
    state = store.snapshot()
    assert len(state['workers']) == 1
    assert state['addresses'][0]['worker_id'] == worker
    assert state['addresses'][0]['valid_from'] == '2026-01-01'
    assert state['addresses'][0]['address']['country'] == ''
    assert import_addresses(store,'unused','2026-01-01',state['revision'])['already_imported']
    assert len(store.snapshot()['addresses']) == 1


def test_duplicate_names_never_automatch(tmp_path,monkeypatch):
    store,_ = setup_store(tmp_path)
    monkeypatch.setattr('app.configuration.addresses.read_addresses',lambda source:('dup',[
        {'row':r,'name':'Voorbeeld Alex','address':address()} for r in (2,3)]))
    assert import_addresses(store,'unused','2026-01-01',store.snapshot()['revision'])['review']==2
    assert not store.snapshot()['addresses']


def test_dated_address_corrections_append_and_keep_history(tmp_path):
    store,worker=setup_store(tmp_path)
    for start,number in [('2026-01-01','12'),('2026-06-01','15'),('2026-06-01','16')]:
        store.apply('address_save',{'worker_id':worker,'valid_from':start,'reason':'Controle','address':{**address(),'number':number,'country':'be'}},store.snapshot()['revision'])
    assert [a['address']['number'] for a in store.snapshot()['addresses']]==['12','15','16']
    assert store.snapshot()['addresses'][-1]['address']['country']=='BE'
    with pytest.raises(ValueError):
        store.apply('address_save',{'worker_id':worker,'valid_from':'2026-03-01','reason':'Controle','address':address()},store.snapshot()['revision'])
    assert len(store.snapshot()['addresses'])==3


def test_existing_addresses_not_overwritten(tmp_path,monkeypatch):
    store,worker=setup_store(tmp_path)
    with store.transaction() as db:append_address(db,worker,'2026-01-01',address(),'Handmatig')
    monkeypatch.setattr('app.configuration.addresses.read_addresses',lambda source:('new',[
        {'row':2,'name':'Voorbeeld Alex','address':{**address(),'number':'99'}}]))
    assert import_addresses(store,'unused','2026-01-01',store.snapshot()['revision'])['review']==1
    state=store.snapshot();candidate=state['address_candidates'][0]
    store.apply('address_ignore',{'candidate_id':candidate['id'],'reason':'Overbodig'},state['revision'])
    assert store.snapshot()['addresses'][0]['address']['number']=='12'
    assert store.snapshot()['address_candidates'][0]['status']=='IGNORED'


def test_manual_link_and_revision_guard(tmp_path,monkeypatch):
    store,worker=setup_store(tmp_path)
    monkeypatch.setattr('app.configuration.addresses.read_addresses',lambda source:('new',[
        {'row':2,'name':'Andere volgorde','address':address()}]))
    import_addresses(store,'unused','2026-01-01',store.snapshot()['revision'])
    state=store.snapshot();data={'candidate_id':state['address_candidates'][0]['id'],'worker_id':worker,'reason':'Naam gecontroleerd'}
    with pytest.raises(ValueError):store.apply('address_link',data,state['revision']-1)
    store.apply('address_link',data,state['revision'])
    assert store.snapshot()['addresses'][0]['worker_id']==worker
    with pytest.raises(ValueError):store.apply('address_link',data,store.snapshot()['revision'])
