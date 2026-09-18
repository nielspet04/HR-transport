import json
import pytest
from app import geocoding
from app.configuration.routes import RouteStore
from test_geocoding import prepared,payload


def test_historical_transport_keeps_later_version(tmp_path):
    store=RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        wid=store.worker(db,'Test Agent')
        rid=db.execute("INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,'Site','site','Auto','auto')",(wid,)).lastrowid
        store.version(db,rid,'2026-09-17','20','Start')
    data={'route_id':rid,'valid_from':'2026-02-01','reason':'HR bevestigt eerdere vervoersperiode','confirm':True}
    with pytest.raises(ValueError):store.apply('route_historical',{**data,'confirm':False},store.snapshot()['revision'])
    store.apply('route_historical',data,store.snapshot()['revision'])
    versions=store.snapshot()['versions']
    assert len(versions)==2
    assert next(v for v in versions if v['valid_from']=='2026-09-17')['kms']=='20'
    assert next(v for v in versions if v['valid_from']=='2026-02-01')['kms'] is None
    with pytest.raises(ValueError):store.apply('route_historical',data,store.snapshot()['revision'])


def test_uncertain_address_requires_explicit_review(tmp_path,monkeypatch):
    store,aid,_=prepared(tmp_path)
    monkeypatch.setattr(geocoding,'token_value',lambda:'pk.fake')
    monkeypatch.setattr(geocoding,'request_address',lambda a:geocoding.parse_response(payload('interpolated')))
    store.apply('address_geocode',{'address_id':aid,'consent':True},store.snapshot()['revision'])
    data={'address_id':aid,'accept':True,'reason':'Adres en punt handmatig gecontroleerd'}
    with pytest.raises(ValueError):store.apply('geocode_review',data,store.snapshot()['revision'])
    store.apply('geocode_review',{**data,'confirm_uncertain':True},store.snapshot()['revision'])
    assert store.snapshot()['addresses'][0]['geocode_status']=='CONFIRMED'
    with store.connect() as db:
        audit=json.loads(db.execute('SELECT details FROM matching_audit ORDER BY id DESC LIMIT 1').fetchone()[0])
        assert audit['confirm_uncertain'] is True
