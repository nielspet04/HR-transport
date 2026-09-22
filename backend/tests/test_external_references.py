import pytest

from app.configuration.external_references import append_reference, effective, import_external_references
from app.configuration.routes import RouteStore


def setup_store(tmp_path):
    store = RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        worker = store.worker(db, 'Voorbeeld Alex')
    return store, worker


def test_dated_reference_changes_keep_history(tmp_path):
    store, worker = setup_store(tmp_path)
    for start, reference in [('2026-01-01','00123'),('2026-07-01','00999'),('2026-07-01','00888')]:
        store.apply('external_reference_save', {'worker_id':worker,'valid_from':start,
            'external_reference':reference,'reason':'HR bevestigt wijziging'}, store.snapshot()['revision'])
    rows = store.snapshot()['external_references']
    assert [row['external_reference'] for row in rows] == ['00123','00999','00888']
    assert effective(rows,worker,'2026-06-30')['external_reference'] == '00123'
    assert effective(rows,worker,'2026-07-01')['external_reference'] == '00888'
    with pytest.raises(ValueError):
        store.apply('external_reference_save', {'worker_id':worker,'valid_from':'2026-06-01',
            'external_reference':'00777','reason':'Te oud'}, store.snapshot()['revision'])


def test_import_reuses_confirmed_address_alias_and_keeps_unknown_candidate(tmp_path,monkeypatch):
    store, worker = setup_store(tmp_path)
    with store.transaction() as db:
        db.execute('INSERT INTO address_imports VALUES(?,?,?)', ('address-source','2026-01-01','{}'))
        db.execute('''INSERT INTO address_candidates(import_hash,source_row,name,address,status,worker_id)
            VALUES(?,?,?,?,?,?)''', ('address-source',2,'Volledige Naam','{}','LINKED',worker))
    monkeypatch.setattr('app.configuration.external_references.read_external_references', lambda source: ('payroll-source',[
        {'row':2,'name':'Volledige Naam','external_reference':'00123'},
        {'row':3,'name':'Onbekend Persoon','external_reference':'00456'}]))
    report = import_external_references(store,'unused','2026-01-01',store.snapshot()['revision'])
    assert report == {'source_rows':2,'linked':1,'review':1}
    state = store.snapshot()
    assert state['external_references'][0]['worker_id'] == worker
    assert state['external_references'][0]['external_reference'] == '00123'
    assert [row['status'] for row in state['external_reference_candidates']] == ['LINKED','REVIEW']
    assert import_external_references(store,'unused','2026-01-01',state['revision'])['already_imported']


def test_manual_candidate_link_and_ignore(tmp_path,monkeypatch):
    store, worker = setup_store(tmp_path)
    monkeypatch.setattr('app.configuration.external_references.read_external_references', lambda source: ('payroll-source',[
        {'row':2,'name':'Andere Naam','external_reference':'00123'},
        {'row':3,'name':'Niet nodig','external_reference':'00456'}]))
    import_external_references(store,'unused','2026-01-01',store.snapshot()['revision'])
    candidates = store.snapshot()['external_reference_candidates']
    store.apply('external_reference_link', {'candidate_id':candidates[0]['id'],'worker_id':worker,
        'reason':'HR bevestigt koppeling'}, store.snapshot()['revision'])
    store.apply('external_reference_ignore', {'candidate_id':candidates[1]['id'],'worker_id':worker,
        'reason':'Niet in vervoerspopulatie'}, store.snapshot()['revision'])
    state = store.snapshot()
    assert [row['status'] for row in state['external_reference_candidates']] == ['LINKED','IGNORED']
    assert state['external_references'][0]['external_reference'] == '00123'
