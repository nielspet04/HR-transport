import pytest
from app.configuration.routes import RouteStore
from app.matching import configuration_digest


def prepared(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    store.apply('route_add',{'name':'Fictief Voorbeeld','location':'PostNL Vilvoorde','mode':'Auto','kms':'17',
                             'valid_from':'2026-01-01','reason':'Test'},store.snapshot()['revision'])
    return store


def data(location='PostNL Vilvoorde',start='2026-01-01',number='12'):
    return {'location':location,'valid_from':start,'reason':'HR bevestigt adres',
            'address':{'street':'Teststraat','number':number,'unit':'','postal_code':'1800','city':'Vilvoorde','country':'be'}}


def test_existing_list_and_shared_airport(tmp_path):
    store=prepared(tmp_path);state=store.snapshot()
    assert any(l['name']=='PostNL Vilvoorde' for l in state['physical_locations'])
    airports=[l for l in state['physical_locations'] if l['key']=='luchthaven']
    assert len(airports)==1 and len(airports[0]['customers'])==5
    store.apply('location_address_save',data('LUCHTHAVEN'),state['revision'])
    saved=store.snapshot()['location_addresses']
    assert len(saved)==1 and saved[0]['location_key']=='luchthaven'


def test_address_does_not_change_matching_or_routes(tmp_path):
    store=prepared(tmp_path);before=store.snapshot()
    store.apply('location_address_save',data('  POSTNL VILVOORDE  '),before['revision'])
    after=store.snapshot()
    assert len(after['location_addresses'])==1
    assert after['location_addresses'][0]['address']['country']=='BE'
    assert after['location_addresses'][0]['location']=='PostNL Vilvoorde'
    for table in ('workers','routes','versions','employee_links','location_links','car_tariffs'):
        assert before[table]==after[table]
    assert configuration_digest(before)==configuration_digest(after)


def test_history_append_and_old_date_guard(tmp_path):
    store=prepared(tmp_path)
    for start,number in [('2026-01-01','12'),('2026-01-01','14'),('2026-06-01','18')]:
        store.apply('location_address_save',data(start=start,number=number),store.snapshot()['revision'])
    assert [v['address']['number'] for v in store.snapshot()['location_addresses']]==['12','14','18']
    with pytest.raises(ValueError):store.apply('location_address_save',data(start='2026-03-01'),store.snapshot()['revision'])
    assert len(store.snapshot()['location_addresses'])==3


@pytest.mark.parametrize('change',[{'location':'Niet bestaande klant'},{'valid_from':'geen datum'},
                                  {'reason':''},{'address':None},{'address':{'country':'BE'}}])
def test_invalid_no_partial_save(tmp_path,change):
    store=prepared(tmp_path);state=store.snapshot()
    with pytest.raises(ValueError):store.apply('location_address_save',{**data(),**change},state['revision'])
    assert not store.snapshot()['location_addresses']
    assert store.snapshot()['revision']==state['revision']


def test_manual_customer_link_uses_existing_physical_location(tmp_path):
    store=prepared(tmp_path)
    with store.transaction() as db:db.execute('INSERT INTO matching_location_links VALUES(?,?)',('nieuwe klant','PostNL Vilvoorde'))
    location=next(l for l in store.snapshot()['physical_locations'] if l['name']=='PostNL Vilvoorde')
    assert location['customers']==['nieuwe klant']
    store.apply('location_address_save',data(),store.snapshot()['revision'])
    assert len(store.snapshot()['location_addresses'])==1


def test_location_geocoding_persists_and_reuses(tmp_path,monkeypatch):
    from app import geocoding
    store=prepared(tmp_path)
    store.apply('location_address_save',data(),store.snapshot()['revision'])
    aid=store.snapshot()['location_addresses'][0]['id'];calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda address:(calls.append(address) or {'status':'REVIEW','longitude':4.4,'latitude':50.9,'eligible':True}))
    assert store.snapshot()['location_geocoding_plan']['requests']==1
    with pytest.raises(ValueError):store.apply('location_geocode',{'address_id':aid},store.snapshot()['revision'])
    assert not calls
    for _ in range(2):store.apply('location_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert len(calls)==1
    assert store.snapshot()['location_addresses'][0]['geocode_status']=='REVIEW'
    assert store.snapshot()['location_geocoding_plan']['requests']==0
    store.apply('location_address_save',data(start='2026-02-01'),store.snapshot()['revision'])
    assert store.snapshot()['location_addresses'][-1]['geocode_status']=='REVIEW'
    store.apply('location_address_save',data(start='2026-03-01',number='99'),store.snapshot()['revision'])
    assert store.snapshot()['location_addresses'][-1]['geocode_status']=='NOT_REQUESTED'
    with pytest.raises(ValueError):store.apply('location_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert len(calls)==1


def test_location_errors_remain_visible_without_retry(tmp_path,monkeypatch):
    from app import geocoding
    store=prepared(tmp_path);store.apply('location_address_save',data(),store.snapshot()['revision'])
    aid=store.snapshot()['location_addresses'][0]['id'];calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    def fail(a):calls.append(a);raise ValueError('Mapbox niet bereikbaar.')
    monkeypatch.setattr(geocoding,'request_address',fail)
    for _ in range(2):store.apply('location_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert len(calls)==1
    assert store.snapshot()['location_addresses'][0]['geocode_status']=='ERROR'
    assert store.snapshot()['location_geocoding_plan']['requests']==0


def test_location_plan_deduplicates_and_skips_future(tmp_path):
    store=prepared(tmp_path)
    store.apply('location_address_save',data(),store.snapshot()['revision'])
    store.apply('location_address_save',data('LUCHTHAVEN'),store.snapshot()['revision'])
    assert store.snapshot()['location_geocoding_plan']['requests']==1
    store.apply('location_address_save',data('LUCHTHAVEN',start='2099-01-01',number='99'),store.snapshot()['revision'])
    assert store.snapshot()['location_geocoding_plan']['requests']==1


def test_location_can_reuse_existing_worker_geocode(tmp_path,monkeypatch):
    from app import geocoding
    from app.configuration.addresses import append_address
    store=prepared(tmp_path)
    store.apply('location_address_save',data(),store.snapshot()['revision'])
    address=store.snapshot()['location_addresses'][0]['address']
    with store.transaction() as db:
        aid=append_address(db,store.snapshot()['workers'][0]['id'],'2026-01-01',address,'Test')
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:{'status':'REVIEW','longitude':4.4,'latitude':50.9,'eligible':True})
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert store.snapshot()['location_geocoding_plan']['requests']==0
    assert store.snapshot()['location_addresses'][0]['geocode_status']=='REVIEW'
