import json

from app.configuration.routes import RouteStore
from app.event_locations import refresh_actions


def prepared(tmp_path,monkeypatch):
    from app import automatic_routes
    monkeypatch.setattr(automatic_routes,'trigger',lambda store:None)
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Voorbeeld Alex','location':'LUCHTHAVEN','mode':'Privé auto',
        'kms':'10','valid_from':'2026-01-01','reason':'Test'},store.snapshot()['revision'])
    worker=store.snapshot()['workers'][0]['id']
    movements=[];locations=[]
    for movement_id,row,start,end in ((1,2,'18:00','22:00'),(2,3,'22:00','23:30')):
        movements.append({'id':movement_id,'planet_id':'100','day':'2026-09-12',
            'source_location':'Event ad hoc','location':None,'employee_status':'MATCHED',
            'location_status':'UNMATCHED_LOCATION','status':'UNMATCHED_LOCATION','routes':[],
            'source_shifts':[{'row':row,'customer':'EVENT AD.HOC','task':'Event',
                'start':start,'end':end,'end_day_offset':None}]})
        locations.append({'customer':'EVENT AD.HOC','physical_location':'EVENT AD.HOC',
            'reference_location':None,'status':'UNMATCHED_LOCATION','movement_id':movement_id,
            'is_ad_hoc':True,'day':'2026-09-12','start':start,'end':end,
            'end_day_offset':None,'planet_id':'100','source_row':row})
    payload={'month':'2026-09','created_at':'test','source_sha256':'event-source',
        'configuration_digest':'old','agents':[{'planet_id':'100','source_names':['Voorbeeld Alex'],
            'source_keys':['voorbeeld alex'],'worker_id':worker,'worker_name':'Voorbeeld Alex',
            'status':'MATCHED','method':'NORMALIZED_NAME','suggestions':[]}],
        'locations':locations,'summary':{},'source_manifest':[], 'movements':movements}
    with store.transaction() as db:
        run=db.execute('INSERT INTO matching_runs(month,created_at,source_path,payload) VALUES(?,?,?,?)',
            ('2026-09','test','unused.xlsx',json.dumps(payload))).lastrowid
    return store,run,worker


def test_legacy_single_location_entry_is_rebuilt_as_two_event_actions(tmp_path,monkeypatch):
    store,run,_=prepared(tmp_path,monkeypatch)
    with store.connect() as db:
        payload=json.loads(db.execute('SELECT payload FROM matching_runs WHERE id=?',(run,)).fetchone()[0])
    payload['locations']=payload['locations'][:1]
    refreshed=refresh_actions(payload)
    assert [(item['movement_id'],item['source_row']) for item in refreshed['locations']]==[(1,2),(2,3)]


def test_existing_location_resolves_only_selected_event_shift(tmp_path,monkeypatch):
    store,run,_=prepared(tmp_path,monkeypatch)
    store.apply('event_location_choice',{'run_id':run,'movement_id':1,'choice':'EXISTING',
        'location':'LUCHTHAVEN','valid_from':'2026-09-12','reason':'Bekende eventlocatie'},
        store.snapshot()['revision'])
    matching=store.get_matching(run)
    assert matching['movements'][0]['location']=='LUCHTHAVEN'
    assert matching['movements'][0]['location_status']=='MATCHED'
    assert matching['movements'][1]['location_status']=='UNMATCHED_LOCATION'
    assert [item['status'] for item in matching['locations']]==['MATCHED','UNMATCHED_LOCATION']


def test_new_event_location_creates_address_route_and_default(tmp_path,monkeypatch):
    store,run,worker=prepared(tmp_path,monkeypatch)
    store.apply('event_location_choice',{'run_id':run,'movement_id':2,'choice':'NEW',
        'location':'Feestzaal Noord','valid_from':'2026-09-12','mode':'Privé auto',
        'address':{'street':'Marktstraat','number':'7','unit':'','postal_code':'1000',
            'city':'Brussel','country':'BE'},'reason':'Nieuwe eenmalige eventlocatie'},
        store.snapshot()['revision'])
    state=store.snapshot()
    assert any(item['location']=='Feestzaal Noord' for item in state['location_addresses'])
    assert any(route['worker_id']==worker and route['location']=='Feestzaal Noord' for route in state['routes'])
    default=next(item for item in state['transport_defaults'] if item['worker_id']==worker and item['location']=='Feestzaal Noord')
    assert default['mode']=='Privé auto' and default['valid_from']=='2026-09-12'
    matching=store.get_matching(run)
    assert matching['movements'][1]['location']=='Feestzaal Noord'
    assert matching['movements'][0]['location_status']=='UNMATCHED_LOCATION'
