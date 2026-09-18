from app.configuration.routes import RouteStore
from app.default_transport import seed


def test_default_car_once_earliest_day_preserves_explicit_transport(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        wid=store.worker(db,'Test Agent')
        db.execute("INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,'Treinsite','treinsite','Trein','trein')",(wid,))
        movement={'planet_id':'1','location':'Nieuwe site','day':'2026-08-14','location_status':'MATCHED'}
        payload={'agents':[{'planet_id':'1','worker_id':wid,'status':'MATCHED'}],
                 'movements':[movement,{**movement,'day':'2026-02-01'},
                              {**movement,'location':'Treinsite'},
                              {**movement,'location':'Onbekend','location_status':'UNMATCHED_LOCATION'}]}
        assert seed(store,db,[payload])==1
        assert seed(store,db,[payload])==0
        r=db.execute("SELECT * FROM routes WHERE location='Nieuwe site'").fetchone()
        assert r['mode']=='Privé auto'
        v=db.execute('SELECT * FROM versions WHERE route_id=?',(r['id'],)).fetchone()
        assert v['valid_from']=='2026-02-01' and v['kms'] is None
        assert db.execute("SELECT count(*) FROM routes WHERE location='Treinsite'").fetchone()[0]==1
        assert not db.execute("SELECT 1 FROM routes WHERE location='Onbekend'").fetchone()


def test_unmatched_worker_never_gets_default(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        payload={'agents':[{'planet_id':'1','worker_id':None,'status':'UNMATCHED_EMPLOYEE'}],
                 'movements':[{'planet_id':'1','location':'Site','day':'2026-08-14','location_status':'MATCHED'}]}
        assert seed(store,db,[payload])==0


def test_source_refresh_seeds_before_publishing_all_months(tmp_path):
    from test_matching import HEADERS,write_xlsx
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Andere Agent','location':'LUCHTHAVEN','mode':'Trein','valid_from':'2026-02-01','reason':'Test'},0)
    with store.transaction() as db:store.worker(db,'Test Agent')
    source=write_xlsx(tmp_path/'planet.xlsx',[list(HEADERS),
        ['123','Test','Agent',None,'2026-08-14','Test','08:00','16:00',None,'TUI',999],
        ['123','Test','Agent',None,'2026-02-10','Test','08:00','16:00',None,'TUI',999]],sheet_name='Total kms')
    store.process_source(source,store.snapshot()['revision'])
    for run in store.snapshot()['matching_runs']:
        payload=store.get_matching(run['id'])
        assert not payload['stale']
        assert payload['movements'][0]['status']=='MATCHED'
        assert payload['movements'][0]['routes'][0]['mode']=='Privé auto'
        assert payload['movements'][0]['routes'][0]['kms'] is None
        assert payload['movements'][0]['routes'][0]['valid_from']=='2026-02-10'
