from app.coverage import check
from test_routing import prepared


def test_source_agent_and_shift_cannot_disappear(tmp_path):
    store,run,p,wid,a=prepared(tmp_path)
    p['source_manifest']=[{'row':99,'planet_id':'missing'}]
    with store.connect() as db:r=check(db,p)
    assert not r['complete']
    assert any(i.get('planet_id')=='missing' for i in r['issues'])
    assert any(i.get('source_rows')==[99] for i in r['issues'])


def test_missing_profile_address_visible_without_dropping_movements(tmp_path):
    store,run,p,wid,a=prepared(tmp_path)
    p['source_manifest']=[]
    p['agents'][0]['worker_id']=None
    with store.connect() as db:r=check(db,p)
    assert len(r['issues'])==1 and r['movements']==1
    p['agents'][0]['worker_id']=wid
    with store.transaction() as db:db.execute('DELETE FROM worker_addresses WHERE worker_id=?',(wid,))
    with store.connect() as db:r=check(db,p)
    assert any('Woonadres' in i['reason'] for i in r['issues'])


def test_valid_profile_and_source_evidence_complete(tmp_path):
    store,run,p,wid,a=prepared(tmp_path)
    p['movements'][0]['source_shifts']=[{'row':99}]
    p['source_manifest']=[{'row':99,'planet_id':'006'}]
    with store.connect() as db:r=check(db,p)
    assert r['complete'] and r['source_checked'] and r['agents']==1
