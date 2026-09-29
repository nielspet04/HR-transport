from app.microsoft_auth import AuthSettings, MicrosoftAuth, SESSION_COOKIE
from argon2 import PasswordHasher


class FakeClient:
    def initiate_auth_code_flow(self, scopes, redirect_uri):
        return {'auth_uri': 'https://login.microsoftonline.com/test', 'state': 'state'}

    def acquire_token_by_auth_code_flow(self, flow, query):
        return {'id_token_claims': {'tid': 'tenant', 'name': 'HR Beheerder',
            'preferred_username': 'hr@example.test', 'oid': 'object',
            'roles': ['HR.Transport.Admin'], 'exp': 4102444800}}


def configured(role='HR.Transport.Admin'):
    return AuthSettings(tenant_id='tenant',client_id='client',client_secret='secret',
        redirect_uri='http://localhost:8081/api/auth/callback',required_role=role)


def local_settings():
    password_hash=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1,
        hash_len=32,salt_len=16).hash('een-veilig-testwachtwoord')
    return AuthSettings(local_username='hr-admin',local_password_hash=password_hash)


def test_disabled_auth_allows_local_user(monkeypatch):
    auth=MicrosoftAuth(AuthSettings())
    assert not auth.enabled
    assert auth.public_status(None)['authenticated']
    assert auth.user(None)['name']=='Lokale beheerder'


def test_authorization_flow_creates_http_only_session():
    auth=MicrosoftAuth(configured());auth._client=FakeClient()
    location,flow_cookie=auth.begin()
    assert location.startswith('https://login.microsoftonline.com/')
    assert 'HttpOnly' in flow_cookie and 'SameSite=Lax' in flow_cookie
    session_cookie=auth.finish(flow_cookie,{'code':'code','state':'state'})
    assert session_cookie.startswith(SESSION_COOKIE+'=')
    user=auth.user(session_cookie)
    assert user['name']=='HR Beheerder' and user['roles']==['HR.Transport.Admin']
    logout,cleared=auth.logout(session_cookie)
    assert '/logout?' in logout and 'Max-Age=0' in cleared
    assert auth.user(session_cookie) is None


def test_wrong_tenant_or_missing_role_is_rejected():
    auth=MicrosoftAuth(configured('Andere.Rol'));auth._client=FakeClient()
    _,flow_cookie=auth.begin()
    try:auth.finish(flow_cookie,{'code':'code','state':'state'})
    except ValueError as error:assert 'geen toegang' in str(error)
    else:raise AssertionError('Ontbrekende rol werd toegelaten')


def test_partial_configuration_fails_closed():
    try:MicrosoftAuth(AuthSettings(tenant_id='tenant'))
    except ValueError as error:assert 'onvolledig' in str(error)
    else:raise AssertionError('Onvolledige configuratie werd stilzwijgend uitgeschakeld')


def test_local_login_creates_session_and_hides_password():
    auth=MicrosoftAuth(local_settings())
    cookie=auth.local_login('HR-ADMIN','een-veilig-testwachtwoord','127.0.0.1')
    assert cookie.startswith(SESSION_COOKIE+'=')
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    assert 'een-veilig-testwachtwoord' not in repr(auth.sessions)
    assert auth.user(cookie)['roles']==['LOCAL_ADMIN']


def test_local_login_uses_generic_error_and_throttles():
    auth=MicrosoftAuth(local_settings())
    for attempt in range(5):
        try:auth.local_login('bestaat-niet','verkeerd','127.0.0.1')
        except ValueError as error:assert str(error)=='Gebruikersnaam of wachtwoord is ongeldig.'
        else:raise AssertionError('Verkeerde gegevens werden toegelaten')
    try:auth.local_login('bestaat-niet','verkeerd','127.0.0.1')
    except PermissionError as error:assert '15 minuten' in str(error)
    else:raise AssertionError('Pogingen werden niet begrensd')


def test_partial_local_configuration_fails_closed():
    try:MicrosoftAuth(AuthSettings(local_username='hr-admin'))
    except ValueError as error:assert 'onvolledig' in str(error)
    else:raise AssertionError('Onvolledige lokale login werd stilzwijgend uitgeschakeld')


def test_http_api_is_closed_without_session(monkeypatch):
    import http.client,json,threading
    from app.configuration.server import make_server
    for key,value in {'ENTRA_TENANT_ID':'tenant','ENTRA_CLIENT_ID':'client','ENTRA_CLIENT_SECRET':'secret',
                      'ENTRA_REDIRECT_URI':'http://localhost:8081/api/auth/callback'}.items():
        monkeypatch.setenv(key,value)
    class Store:
        def snapshot(self):return {'secret_hr_data':True}
    server=make_server(Store(),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request('GET','/api/auth/status');response=client.getresponse()
        assert response.status==200 and json.loads(response.read())['authenticated'] is False
        client.request('GET','/api/state');response=client.getresponse()
        assert response.status==401 and 'Meld je aan' in json.loads(response.read())['error']
    finally:
        client.close();server.shutdown();server.server_close();thread.join(timeout=2)


def test_http_local_login_unlocks_api(monkeypatch):
    import http.client,json,threading
    from app.configuration.server import make_server
    settings=local_settings()
    monkeypatch.setenv('LOCAL_AUTH_USERNAME',settings.local_username)
    monkeypatch.setenv('LOCAL_AUTH_PASSWORD_HASH',settings.local_password_hash)
    class Store:
        def snapshot(self):return {'secret_hr_data':True}
    server=make_server(Store(),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request('GET','/api/auth/status');response=client.getresponse()
        status=json.loads(response.read())
        assert response.status==200 and status['provider']=='local' and not status['authenticated']
        client.request('GET','/api/state');response=client.getresponse()
        assert response.status==401;response.read()
        body=json.dumps({'username':'hr-admin','password':'een-veilig-testwachtwoord'})
        client.request('POST','/api/auth/local-login',body,{'Content-Type':'application/json'})
        response=client.getresponse();cookie=response.getheader('Set-Cookie')
        assert response.status==200 and cookie and 'HttpOnly' in cookie;response.read()
        client.request('GET','/api/state',headers={'Cookie':cookie})
        response=client.getresponse()
        assert response.status==200 and json.loads(response.read())['secret_hr_data'] is True
    finally:
        client.close();server.shutdown();server.server_close();thread.join(timeout=2)
