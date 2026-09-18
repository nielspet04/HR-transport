import json
import pytest
from test_routing import prepared


def test_excluded_month_hidden_and_not_routed_but_preserved(tmp_path):
    store,run,p,wid,addr=prepared(tmp_path)
    january=json.loads(json.dumps(p))
    january['month']='2026-01'
    for movement in january['movements']:
        movement['day']='2026-01-01'
    with store.transaction() as db:
        jan=store.insert_matching(db,january,'source.xlsx')
        db.execute('INSERT INTO excluded_months VALUES(?,?)',('2026-01','Gebruiker sluit januari uit'))
    assert store.get_route_plan(run)['months']==['2026-08']
    snapshot=store.snapshot()
    assert all(r['month']!='2026-01' for r in snapshot['matching_runs'])
    assert snapshot['matching']['month']=='2026-08'
    with pytest.raises(ValueError):store.get_matching(jan)
    with pytest.raises(ValueError):store.get_route_plan(jan)
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM matching_runs WHERE id=?',(jan,)).fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM workers WHERE id=?',(wid,)).fetchone()[0]==1
