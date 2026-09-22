from app.transport_defaults import effective
from test_matching import config,imported,RULES,shift
from app.matching import match_import


def test_dated_default_replaces_route_modes_without_deleting_them():
    c=config();c['transport_defaults']=[{'id':1,'worker_id':1,'location':'LUCHTHAVEN','location_key':'luchthaven','mode':'Mob budget','valid_from':'2026-08-01','reason':'HR','changed_at':'x'}]
    result=match_import(imported(shift(customer='TUI')),c,RULES)
    movement=result['movements'][0]
    assert movement['status']=='MATCHED'
    assert [r['mode'] for r in movement['routes']]==['Mob budget']
    assert any(r['mode']=='Fiets' for r in c['routes'])


def test_effective_default_is_location_and_date_specific():
    rows=[{'id':1,'worker_id':2,'location_key':'site','valid_from':'2026-01-01','mode':'Trein'},
          {'id':2,'worker_id':2,'location_key':'site','valid_from':'2026-09-01','mode':'Fiets'},
          {'id':3,'worker_id':3,'location_key':'site','valid_from':'2026-01-01','mode':'Mob budget'}]
    assert effective(rows,2,'Site','2026-08-01')['mode']=='Trein'
    assert effective(rows,2,'Site','2026-09-01')['mode']=='Fiets'
    assert effective(rows,3,'Site','2026-08-01')['mode']=='Mob budget'
