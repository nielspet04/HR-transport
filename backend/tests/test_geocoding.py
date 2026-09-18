import json
import pytest
from app import geocoding
from app.configuration.routes import RouteStore
from app.configuration.addresses import append_address


def address():
    return dict(street='Teststraat',number='12',unit='',postal_code='1000',city='Brussel',country='BE')


def payload(accuracy='rooftop', number='matched', country='be'):
    return {'features':[{'properties':{'feature_type':'address','name':'Teststraat 12',
        'coordinates':{'longitude':4.35,'latitude':50.85,'accuracy':accuracy},
        'context':{'country':{'country_code':country}},
        'match_code':{'address_number':number,'street':'matched','postcode':'matched','confidence':'exact'}}}]}


def prepared(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        worker=store.worker(db,'Fictief Voorbeeld')
        aid=append_address(db,worker,'2026-01-01',address(),'Test')
    return store,aid,worker


def test_precise_match_still_requires_review():
    r=geocoding.parse_response(payload())
    assert r['status']=='REVIEW' and r['eligible']


@pytest.mark.parametrize('accuracy,number',[('interpolated','matched'),('rooftop','unmatched'),('approximate','matched')])
def test_imprecise_match_cannot_be_confirmed(accuracy,number):
    assert not geocoding.parse_response(payload(accuracy,number))['eligible']


@pytest.mark.parametrize('country',['nl',''])
def test_foreign_or_missing_country_rejected(country):
    with pytest.raises(ValueError):geocoding.parse_response(payload(country=country))


def test_empty_result():
    assert geocoding.parse_response({'features':[]})['status']=='NO_MATCH'


def test_consent_revision_cache_history_and_review(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path);calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:(calls.append(a) or geocoding.parse_response(payload())))
    data={'address_id':aid,'consent':True}
    rev=store.snapshot()['revision']
    with pytest.raises(ValueError):store.apply('address_geocode',{'address_id':aid},rev)
    with pytest.raises(ValueError):store.apply('address_geocode',data,rev-1)
    assert not calls
    store.apply('address_geocode',data,rev)
    assert store.snapshot()['addresses'][0]['geocode_status']=='REVIEW'
    store.apply('address_geocode',data,store.snapshot()['revision'])
    assert len(calls)==1
    store.apply('geocode_review',{'address_id':aid,'accept':True,'reason':'Adres gecontroleerd'},store.snapshot()['revision'])
    assert store.snapshot()['addresses'][0]['geocode_status']=='CONFIRMED'
    with store.transaction() as db:
        append_address(db,worker,'2026-02-01',address(),'Zelfde adres')
        append_address(db,worker,'2026-03-01',{**address(),'number':'99'},'Verhuis')
    assert [a['geocode_status'] for a in store.snapshot()['addresses']]==['CONFIRMED','CONFIRMED','NOT_REQUESTED']
    assert 'pk.fake' not in json.dumps(store.snapshot())


def test_errors_saved_without_retry(tmp_path,monkeypatch):
    store,aid,_=prepared(tmp_path);calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    def fail(a):
        calls.append(a)
        raise ValueError('Mapbox niet bereikbaar.')
    monkeypatch.setattr(geocoding,'request_address',fail)
    for _ in range(2):store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert len(calls)==1
    assert store.snapshot()['addresses'][0]['geocode_status']=='ERROR'


def test_query_permanent_and_contains_no_identity(monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    captured={}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):return json.dumps(payload()).encode()
    class Opener:
        def open(self,url,timeout):
            captured.update(parse_qs(urlsplit(url).query));return Response()
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'build_opener',lambda *args:Opener())
    geocoding.request_address(address())
    assert captured['permanent']==['true'] and captured['country']==['be']
    assert set(captured)=={'access_token','permanent','autocomplete','types','limit','country','address_number','street','postcode','place'}


def test_bulk_plan_current_only_deduplicated_and_cached(tmp_path):
    store,aid,worker=prepared(tmp_path)
    with store.transaction() as db:
        append_address(db,worker,'2026-02-01',{**address(),'number':'99'},'Verhuis')
        append_address(db,worker,'2027-01-01',{**address(),'number':'100'},'Toekomst')
        other=store.worker(db,'Zelfde Gebouw')
        append_address(db,other,'2026-01-01',{**address(),'number':'99'},'Test')
        foreign=store.worker(db,'Land Onbekend')
        append_address(db,foreign,'2026-01-01',{**address(),'country':''},'Test')
    addresses=store.snapshot()['addresses']
    plan=geocoding.bulk_plan(addresses,today='2026-09-18')
    assert plan['requests']==1 and plan['current_profiles']==3 and plan['blocked_profiles']==1
    assert aid not in plan['address_ids']
    current_id=plan['address_ids'][0]
    assert next(a for a in addresses if a['id']==current_id)['address']['number']=='99'
    for a in addresses:
        if a['address']['number']=='99':a['geocode']={'status':'REVIEW'}
    plan=geocoding.bulk_plan(addresses,today='2026-09-18')
    assert plan['requests']==0 and plan['existing_profiles']==2


def test_bulk_stale_address_never_sent(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path);calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:(calls.append(a) or geocoding.parse_response(payload())))
    with store.transaction() as db:append_address(db,worker,'2026-01-01',{**address(),'number':'99'},'Correctie')
    with pytest.raises(ValueError):store.apply('address_geocode_bulk_item',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    assert not calls


def test_bulk_results_survive_later_failure_and_skip_cached(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path)
    with store.transaction() as db:
        other=store.worker(db,'Tweede Werknemer')
        second=append_address(db,other,'2026-01-01',{**address(),'number':'99'},'Test')
    calls=[]
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    def request(a):
        calls.append(a)
        if a['number']=='99':raise ValueError('Mapbox niet bereikbaar.')
        return geocoding.parse_response(payload())
    monkeypatch.setattr(geocoding,'request_address',request)
    for address_id in (aid,second,aid):
        store.apply('address_geocode_bulk_item',{'address_id':address_id,'consent':True},store.snapshot()['revision'])
    assert len(calls)==2
    state=store.snapshot()
    assert [a['geocode_status'] for a in state['addresses']]==['REVIEW','ERROR']
    assert state['geocoding_bulk_plan']['requests']==0


def test_review_many_atomic_validation_and_shared_result(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:geocoding.parse_response(payload()))
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    with store.transaction() as db:
        other=store.worker(db,'Zelfde Adres')
        duplicate=append_address(db,other,'2026-01-01',address(),'Test')
        third=store.worker(db,'Ongecontroleerd')
        missing=append_address(db,third,'2026-01-01',{**address(),'number':'99'},'Test')
    for ids in ([aid,missing],[aid,aid],[],[True],[999]):
        with pytest.raises(ValueError):store.apply('geocode_review_many',{'address_ids':ids,'accept':True,'reason':'Gecontroleerd'},store.snapshot()['revision'])
        assert store.snapshot()['addresses'][0]['geocode_status']=='REVIEW'
    store.apply('geocode_review_many',{'address_ids':[aid,duplicate],'accept':True,'reason':'Bron en gevonden adres vergeleken'},store.snapshot()['revision'])
    assert [a['geocode_status'] for a in store.snapshot()['addresses']]==['CONFIRMED','CONFIRMED','NOT_REQUESTED']
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM address_geocodes').fetchone()[0]==1
        assert db.execute('SELECT reason FROM address_geocodes').fetchone()[0]=='Bron en gevonden adres vergeleken'


def test_review_many_rejects_weak_match_confirmation(tmp_path,monkeypatch):
    store,aid,_=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:geocoding.parse_response(payload(accuracy='interpolated')))
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    data={'address_ids':[aid],'accept':True,'reason':'Test'}
    with pytest.raises(ValueError):store.apply('geocode_review_many',data,store.snapshot()['revision'])
    assert store.snapshot()['addresses'][0]['geocode_status']=='REVIEW'
    store.apply('geocode_review_many',{**data,'accept':False},store.snapshot()['revision'])
    assert store.snapshot()['addresses'][0]['geocode_status']=='REJECTED'


def test_review_many_requires_reason_current_version_and_revision(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:geocoding.parse_response(payload()))
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    data={'address_ids':[aid],'accept':True,'reason':'Test'}
    with pytest.raises(ValueError):store.apply('geocode_review_many',{**data,'reason':''},store.snapshot()['revision'])
    with pytest.raises(ValueError):store.apply('geocode_review_many',data,store.snapshot()['revision']-1)
    with store.transaction() as db:append_address(db,worker,'2026-01-01',{**address(),'number':'99'},'Correctie')
    with pytest.raises(ValueError):store.apply('geocode_review_many',data,store.snapshot()['revision'])
    assert store.snapshot()['addresses'][0]['geocode_status']=='REVIEW'


def test_explicit_user_review_overrides_confidence_not_missing(tmp_path,monkeypatch):
    store,aid,worker=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:geocoding.parse_response(payload(accuracy='interpolated')))
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    with store.transaction() as db:
        other=store.worker(db,'Geen Match')
        missing=append_address(db,other,'2026-01-01',{**address(),'number':'99'},'Test')
    monkeypatch.setattr(geocoding,'request_address',lambda a:{'status':'NO_MATCH'})
    store.apply('address_geocode',{'address_id':missing,'consent':True},store.snapshot()['revision'])
    with pytest.raises(ValueError):geocoding.confirm_hand_checked_current(store,store.snapshot()['revision'],user_confirmed=False,reason='Test')
    report=geocoding.confirm_hand_checked_current(store,store.snapshot()['revision'],user_confirmed=True,reason='Gebruiker heeft alle resultaten gecontroleerd')
    assert report=={'confirmed_results':1,'confidence_overrides':1,'missing_profiles':1}
    assert [a['geocode_status'] for a in store.snapshot()['addresses']]==['CONFIRMED','NO_MATCH']
    assert not store.snapshot()['addresses'][0]['geocode']['result']['eligible']


def test_manual_confirmation_rejects_invalid_coordinates(tmp_path,monkeypatch):
    store,aid,_=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:{'status':'REVIEW','longitude':999,'latitude':50,'eligible':False})
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    with pytest.raises(ValueError):geocoding.confirm_hand_checked_current(store,store.snapshot()['revision'],user_confirmed=True,reason='Test')
    assert store.snapshot()['addresses'][0]['geocode_status']=='REVIEW'
