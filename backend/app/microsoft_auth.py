"""Microsoft Entra ID authorization-code authentication for the local HTTP server."""
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict, deque
from http.cookies import SimpleCookie
import hmac
import os
import secrets
import time
from urllib.parse import urlencode
from pathlib import Path


SESSION_COOKIE = 'hr_transport_session'
FLOW_COOKIE = 'hr_transport_auth_flow'


@dataclass(frozen=True)
class AuthSettings:
    tenant_id: str = ''
    client_id: str = ''
    client_secret: str = ''
    certificate_path: str = ''
    certificate_thumbprint: str = ''
    redirect_uri: str = ''
    required_role: str = ''
    post_logout_uri: str = ''
    secure_cookie: bool = False
    local_username: str = ''
    local_password_hash: str = ''
    session_idle_minutes: int = 30

    @property
    def entra_enabled(self):
        credential = self.client_secret or (self.certificate_path and self.certificate_thumbprint)
        return bool(self.tenant_id and self.client_id and credential and self.redirect_uri)

    @property
    def local_enabled(self):
        return bool(self.local_username and self.local_password_hash)

    @property
    def enabled(self):
        return self.entra_enabled or self.local_enabled

    @classmethod
    def from_env(cls):
        redirect = os.getenv('ENTRA_REDIRECT_URI', '').strip()
        return cls(
            tenant_id=os.getenv('ENTRA_TENANT_ID', '').strip(),
            client_id=os.getenv('ENTRA_CLIENT_ID', '').strip(),
            client_secret=os.getenv('ENTRA_CLIENT_SECRET', '').strip(),
            certificate_path=os.getenv('ENTRA_CLIENT_CERTIFICATE_PATH', '').strip(),
            certificate_thumbprint=os.getenv('ENTRA_CLIENT_CERTIFICATE_THUMBPRINT', '').strip(),
            redirect_uri=redirect,
            required_role=os.getenv('ENTRA_REQUIRED_ROLE', '').strip(),
            post_logout_uri=os.getenv('ENTRA_POST_LOGOUT_URI', '').strip() or redirect.removesuffix('/api/auth/callback'),
            secure_cookie=os.getenv('AUTH_COOKIE_SECURE', os.getenv('ENTRA_COOKIE_SECURE', '')).strip().lower() in ('1', 'true', 'yes') or redirect.startswith('https://'),
            local_username=os.getenv('LOCAL_AUTH_USERNAME', '').strip(),
            local_password_hash=os.getenv('LOCAL_AUTH_PASSWORD_HASH', '').strip(),
            session_idle_minutes=int(os.getenv('AUTH_SESSION_IDLE_MINUTES', '30')))


class MicrosoftAuth:
    def __init__(self, settings=None):
        self.settings = settings or AuthSettings.from_env()
        entra_configured = any((self.settings.tenant_id, self.settings.client_id, self.settings.client_secret,
                          self.settings.certificate_path, self.settings.certificate_thumbprint,
                          self.settings.redirect_uri, self.settings.required_role))
        local_configured = bool(self.settings.local_username or self.settings.local_password_hash)
        if entra_configured and not self.settings.entra_enabled:
            raise ValueError('Microsoft-login is onvolledig geconfigureerd; toegang wordt uit veiligheid niet gestart.')
        if local_configured and not self.settings.local_enabled:
            raise ValueError('Lokale login is onvolledig geconfigureerd; toegang wordt uit veiligheid niet gestart.')
        if not 5 <= self.settings.session_idle_minutes <= 120:
            raise ValueError('De sessie-time-out moet tussen 5 en 120 minuten liggen.')
        self.sessions = {}
        self.flows = {}
        self.failures = defaultdict(deque)
        self._client = None
        self._password_hasher = None
        self._dummy_hash = None

    @property
    def enabled(self):
        return self.settings.enabled

    @property
    def provider(self):
        return 'microsoft' if self.settings.entra_enabled else 'local' if self.settings.local_enabled else 'none'

    @property
    def authority(self):
        return f'https://login.microsoftonline.com/{self.settings.tenant_id}'

    def _app(self):
        if self._client is None:
            try:
                import msal
            except ImportError as error:
                raise RuntimeError('Installeer de projectafhankelijkheden om Microsoft-login te gebruiken.') from error
            credential = self.settings.client_secret
            if self.settings.certificate_path:
                try:private_key = Path(self.settings.certificate_path).read_text(encoding='utf-8')
                except OSError as error:raise RuntimeError('Het geconfigureerde Microsoft-certificaat kan niet worden gelezen.') from error
                credential = {'private_key': private_key, 'thumbprint': self.settings.certificate_thumbprint}
            self._client = msal.ConfidentialClientApplication(
                self.settings.client_id, authority=self.authority,
                client_credential=credential)
        return self._client

    @staticmethod
    def _cookies(header):
        parsed = SimpleCookie()
        if header:
            try:parsed.load(header)
            except Exception:return {}
        return {key: morsel.value for key, morsel in parsed.items()}

    def _cookie(self, name, value, max_age):
        parts = [f'{name}={value}', 'Path=/', 'HttpOnly', 'SameSite=Lax', f'Max-Age={max_age}']
        if self.settings.secure_cookie:
            parts.append('Secure')
        return '; '.join(parts)

    def begin(self):
        if self.provider != 'microsoft':
            raise ValueError('Microsoft-login is niet geconfigureerd.')
        key = secrets.token_urlsafe(32)
        flow = self._app().initiate_auth_code_flow([], redirect_uri=self.settings.redirect_uri)
        if 'auth_uri' not in flow:
            raise ValueError('Microsoft-login kon niet worden gestart.')
        self.flows[key] = flow
        return flow['auth_uri'], self._cookie(FLOW_COOKIE, key, 600)

    def finish(self, cookie_header, query):
        cookies = self._cookies(cookie_header)
        flow = self.flows.pop(cookies.get(FLOW_COOKIE, ''), None)
        if not flow:
            raise ValueError('De Microsoft-aanmelding is verlopen. Start opnieuw.')
        try:
            result = self._app().acquire_token_by_auth_code_flow(flow, query)
        except ValueError as error:
            raise ValueError('De Microsoft-aanmelding kon niet veilig worden bevestigd.') from error
        claims = result.get('id_token_claims') or {}
        if 'error' in result or not claims:
            raise ValueError(result.get('error_description') or 'Microsoft heeft de aanmelding niet bevestigd.')
        if claims.get('tid') != self.settings.tenant_id:
            raise ValueError('Dit Microsoft-account behoort niet tot de toegelaten organisatie.')
        roles = claims.get('roles') or []
        if self.settings.required_role and self.settings.required_role not in roles:
            raise ValueError('Dit Microsoft-account heeft geen toegang tot HR Vervoerskosten.')
        expires = min(int(claims.get('exp') or 0), int(datetime.now(timezone.utc).timestamp()) + 8 * 3600)
        if expires <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError('De Microsoft-aanmelding is al verlopen.')
        return self._new_session({
            'name': claims.get('name') or claims.get('preferred_username') or 'Microsoft-gebruiker',
            'username': claims.get('preferred_username') or '',
            'tenant_id': claims.get('tid'), 'object_id': claims.get('oid'), 'roles': roles}, expires)

    def _new_session(self, user, expires=None):
        now = int(time.time()); expires = expires or now + 8 * 3600
        token = secrets.token_urlsafe(48)
        self.sessions[token] = {'expires': expires, 'last_seen': now, 'user': user}
        return self._cookie(SESSION_COOKIE, token, expires - now)

    def _hasher(self):
        if self._password_hasher is None:
            try:
                from argon2 import PasswordHasher
            except ImportError as error:
                raise RuntimeError('Installeer de projectafhankelijkheden om lokale login te gebruiken.') from error
            self._password_hasher = PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1,hash_len=32,salt_len=16)
            self._dummy_hash = self._password_hasher.hash('geen-geldig-lokaal-wachtwoord')
        return self._password_hasher

    def local_login(self, username, password, remote):
        if self.provider != 'local':
            raise ValueError('Lokale login is niet actief.')
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>250 or len(password)>1024:
            raise ValueError('Gebruikersnaam of wachtwoord is ongeldig.')
        normalized = username.strip().casefold()
        account_key, remote_key = 'account:'+normalized, 'remote:'+str(remote)
        now = time.monotonic()
        for key in (account_key, remote_key):
            attempts = self.failures[key]
            while attempts and attempts[0] < now - 900:attempts.popleft()
            if len(attempts) >= 5:
                raise PermissionError('Te veel mislukte pogingen. Probeer over 15 minuten opnieuw.')
        expected_user = self.settings.local_username.strip().casefold()
        hasher = self._hasher()
        correct_user = hmac.compare_digest(normalized, expected_user)
        candidate_hash = self.settings.local_password_hash if correct_user else self._dummy_hash
        valid = False
        try:valid = hasher.verify(candidate_hash,password)
        except Exception:valid = False
        if not valid or not correct_user:
            self.failures[account_key].append(now);self.failures[remote_key].append(now)
            raise ValueError('Gebruikersnaam of wachtwoord is ongeldig.')
        self.failures.pop(account_key,None);self.failures.pop(remote_key,None)
        return self._new_session({'name': self.settings.local_username, 'username': self.settings.local_username,
                                  'tenant_id': None, 'object_id': None, 'roles': ['LOCAL_ADMIN']})

    def user(self, cookie_header):
        if not self.enabled:
            return {'name': 'Lokale beheerder', 'username': '', 'roles': []}
        token = self._cookies(cookie_header).get(SESSION_COOKIE)
        session = self.sessions.get(token)
        now = int(datetime.now(timezone.utc).timestamp())
        idle_seconds = self.settings.session_idle_minutes * 60
        if not session or session['expires'] <= now or session['last_seen'] + idle_seconds <= now:
            if token:self.sessions.pop(token, None)
            return None
        session['last_seen'] = now
        return session['user']

    def logout(self, cookie_header):
        token = self._cookies(cookie_header).get(SESSION_COOKIE)
        if token:self.sessions.pop(token, None)
        cleared = self._cookie(SESSION_COOKIE, '', 0)
        target = (f'{self.authority}/oauth2/v2.0/logout?{urlencode({"post_logout_redirect_uri": self.settings.post_logout_uri})}'
                  if self.provider == 'microsoft' else '/')
        return target, cleared

    def public_status(self, cookie_header):
        user = self.user(cookie_header)
        return {'enabled': self.enabled, 'provider': self.provider, 'authenticated': bool(user),
                'user': user if user else None, 'required_role': self.settings.required_role or None}
