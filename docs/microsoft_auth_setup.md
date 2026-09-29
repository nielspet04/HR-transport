# Aanmelden bij HR Vervoerskosten

## Tijdelijke lokale login

Zolang de Entra-appregistratie nog niet beschikbaar is, kan de applicatie met
een lokaal beheeraccount worden afgeschermd. Het wachtwoord wordt nooit in de
code of database opgeslagen: alleen een Argon2id-hash staat in een
omgevingsvariabele.

Genereer de hash interactief. Het wachtwoord wordt verborgen ingevoerd en niet
naar de shellgeschiedenis geschreven:

```bash
.venv/bin/python scripts/generate_local_password_hash.py
```

Stel daarna de gebruiker en de volledige gegenereerde hash in. Gebruik enkele
aanhalingstekens rond de hash, zodat de `$`-tekens niet door de shell worden
verwerkt:

```bash
export LOCAL_AUTH_USERNAME="hr-admin"
export LOCAL_AUTH_PASSWORD_HASH='$argon2id$...volledige-gegenereerde-waarde...'
export AUTH_SESSION_IDLE_MINUTES="30"
export AUTH_COOKIE_SECURE="false" # uitsluitend voor localhost zonder HTTPS
.venv/bin/python scripts/manage_transport.py --require-auth
```

Op een server is HTTPS verplicht en moet `AUTH_COOKIE_SECURE="true"` worden
gebruikt. Na vijf mislukte pogingen wordt de account/IP-combinatie vijftien
minuten geblokkeerd. Sessies verlopen na maximaal acht uur en al na de
ingestelde periode zonder activiteit. Bij een serverherstart vervallen alle
sessies.

Zodra Entra volledig is ingesteld, krijgt Microsoft-login automatisch
voorrang. Verwijder dan `LOCAL_AUTH_USERNAME` en `LOCAL_AUTH_PASSWORD_HASH` uit
de serveromgeving.

## Microsoft 365 / Entra ID-login

De definitieve configuratie gebruikt Microsoft Entra ID als identity provider.
Er worden dan geen lokale gebruikersnamen of wachtwoorden gebruikt. Alle `/api/*`-routes,
downloads, kaartbeelden en wijzigingen vereisen na configuratie een geldige
server-side sessie.

## 1. App registreren

1. Open **Microsoft Entra admin center → Identity → Applications → App registrations**.
2. Maak `ICTS HR Vervoerskosten` als **single-tenant** toepassing.
3. Noteer de **Application (client) ID** en **Directory (tenant) ID**.
4. Voeg bij **Authentication → Web** deze redirect URI toe:
   `http://localhost:8081/api/auth/callback`.
5. Voeg voor productie ook exact `https://JOUW-DOMEIN/api/auth/callback` toe.
   Activeer geen implicit/hybrid tokens.

## 2. Toegang beperken tot HR

Maak onder **App roles** een gebruikersrol met waarde `HR.Transport.Admin`.
Ga daarna naar **Enterprise applications → ICTS HR Vervoerskosten → Users and
groups** en wijs uitsluitend de bevoegde HR-gebruikers of HR-groep aan deze rol
toe. Zet bij **Properties** ook *Assignment required?* op **Yes**.

## 3. Servercredential

Voor lokaal testen kan een client secret worden gebruikt. Bewaar alleen de
secretwaarde in een omgevingsvariabele; zet die nooit in Git. Gebruik op de
productieserver bij voorkeur een certificaat:

```bash
export ENTRA_TENANT_ID="directory-tenant-id"
export ENTRA_CLIENT_ID="application-client-id"
export ENTRA_CLIENT_SECRET="secretwaarde"
export ENTRA_REDIRECT_URI="http://localhost:8081/api/auth/callback"
export ENTRA_POST_LOGOUT_URI="http://localhost:8081/"
export ENTRA_REQUIRED_ROLE="HR.Transport.Admin"
export AUTH_COOKIE_SECURE="false"
```

Voor een HTTPS-productieserver vervang je het secret door:

```bash
export ENTRA_CLIENT_CERTIFICATE_PATH="/beveiligd/pad/entra-private-key.pem"
export ENTRA_CLIENT_CERTIFICATE_THUMBPRINT="CERTIFICAAT_THUMBPRINT"
export AUTH_COOKIE_SECURE="true"
```

Start een beveiligde omgeving altijd met:

```bash
.venv/bin/python scripts/manage_transport.py --require-auth
```

Met `--require-auth` weigert de applicatie te starten als een instelling of
credential ontbreekt. Zonder Entra-variabelen blijft de huidige lokale
ontwikkelmodus werken.

## Beveiligingsgedrag

- Authorization Code Flow via Microsoft; wachtwoorden bereiken de applicatie nooit.
- De Microsoft tenant-ID en optionele app-rol worden na login gecontroleerd.
- Sessiecookies zijn `HttpOnly` en `SameSite=Lax`; bij HTTPS ook `Secure`.
- Sessies verlopen uiterlijk na acht uur en verdwijnen bij een serverherstart.
- Bestaande CSRF-controle blijft voor alle schrijfacties actief.
