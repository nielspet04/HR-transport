# Fase 3 — eenvoudig routebeheer

Deze werkwijze vervangt de eerdere complexe kandidaat-/conflictworkflow. Het dashboard gebruikt uitsluitend de nieuwe Sociaal-abo-Excel als startbron, geen Planet-export, tarieven of overige HR-kolommen.

Fase 4 heeft daarnaast een apart tabblad Maandshiften. Dat koppelt een gekozen Planet-maand aan deze routes, zonder de fase-3-brongegevens te wijzigen. Zie `phase_4.md`.

## Starten

Stop de oude dashboardserver met Ctrl+C en start vanuit de projectmap:

```bash
.venv/bin/python scripts/manage_transport.py
```

Open `http://127.0.0.1:8765`. Alleen herladen stopt de oude Python-server niet. Bij Address already in use draait er nog een server op deze poort.

De nieuwe bron is al geladen: 146 bronregels, 62 werknemers na normaliseren van namen, 143 routes na drie identieke dubbels en één onzekere afstand. De beginversies gelden vanaf 1 februari 2026. Eén route is **werknemer + fysieke locatie + vervoerswijze**. Fiets en auto kunnen dus verschillende kilometers hebben zonder conflict.

## Wat wordt gebruikt?

Alleen `Naam`, `Locatie`, `Afstand`, `Vervoerswijze` van blad `Niels`. `DS1`, externe referenties, Rijksregisternummer en overige kolommen worden niet gekopieerd naar de database. Geen forward-fill of gegokte ontbrekende waarden. Namen worden samengevoegd op hoofdletter-/spatiegenormaliseerde gelijkheid binnen deze bron, niet gekoppeld aan Planet-IDs. Gelijke namen van verschillende mensen vereisen later een eigen stabiele identiteit.

APT en APT Fiets zijn expliciet LUCHTHAVEN; WeWork Fiets wordt WeWork. Andere locaties blijven de aangeleverde locaties, met overtollige spaties verwijderd. Vervoerlabels blijven zoals aangeleverd, ook Auto en Mob budget: dit kiest nog geen vergoeding of privéautocategorie. De band 37-39 blijft letterlijk zichtbaar als Nakijken, niet als 38 of 39. Exacte dubbels worden één route met behoud van bronrijnummers. Tegenstrijdige afstanden binnen dezelfde route blijven onzeker.

## Bediening

- Zoek in de lijst op werknemer, locatie of vervoer.
- Klik Aanpassen om de afstand te wijzigen. Kies bewust Geldig vanaf en een reden.
- Klik Werknemer / route toevoegen voor een nieuw persoon of een extra locatie/vervoerswijze bij een bestaande werknemer. Vul een bestaande naam exact in of gebruik de suggestie. Voor een andere vervoerswijze voeg je een aparte route toe.
- Onder Werknemernaam aanpassen kun je de naam bij alle routes van die persoon wijzigen.
- Onder Verhuizing kies je een werknemer en vult voor iedere locatie/vervoerswijze een nieuwe afstand in. Alle routes worden samen opgeslagen of geen enkele bij ongeldige invoer.
- Situatie op datum en Historie tonen maken oude afstandsversies controleerbaar. Een toekomstige route wordt zichtbaar als Toekomstig, niet als reeds geldig.

Een latere ingangsdatum maakt een nieuwe versie. Corrigeer je opnieuw op dezelfde laatste ingangsdatum, dan blijft de vorige waarde in het correctielog bewaard; de huidige versie wordt bijgewerkt. Een wijziging vóór de laatste ingangsdatum wordt geweigerd om tussengevoegde historische versies te voorkomen. Kies de oorspronkelijke startdatum alleen bewust voor een broncorrectie; kies bij een echte verhuizing de verhuisdatum.

Het gebruikte vervoer per daadwerkelijke shift wordt in deze fase nog niet bepaald. Meerdere opgeslagen routes betekenen niet dat we weten welke die dag gebruikt werd.

## Opslag en opnieuw importeren

Nieuwe opslag: `data/state/routes.sqlite3`. Oude opslag: `data/state/transport.sqlite3`, met extra back-up `data/state/legacy-before-simplified-routes-2026-09-17.sqlite3`. De oude wijzigingen zijn niet verwijderd of automatisch overgenomen. De oude interface is desgewenst afzonderlijk te openen met `--legacy`.

Dezelfde bron opnieuw laden is idempotent en overschrijft geen aanpassingen. Een andere bron die bestaande routes zou vervangen wordt geweigerd: vervanging moet bewust met een aparte database of gecontroleerde migratie gebeuren. Dit voorkomt verlies van handmatig beheerde kilometers.

Voor een nieuwe lege installatie:

```bash
.venv/bin/python scripts/manage_transport.py --reference "/pad/naar/VERVOER Sociaal abo vanaf 01.02.2026 (1).xlsx" --confirm-reference-from 2026-02-01 --seed-only
```

Andere bladnaam? Geef `--sheet BLADNAAM` mee. De startdatum wordt bewust als parameter gekozen, niet uit onnodige datumkolommen geraden.

Back-up van nieuw beheer:

```bash
.venv/bin/python scripts/manage_transport.py --seed-only --backup data/state/routes-backup-2026-09-17.sqlite3
```

Gebruik telkens een nieuwe bestandsnaam; bestaande back-ups worden niet overschreven. Databases/back-ups zijn Git-genegeerd. Het dashboard is alleen lokaal op een vertrouwde computer, zonder login; niet publiek hosten.

## Code

- `backend/app/importers/reference.py`: bronblad en vier velden, met routebewuste interpretatie.
- `backend/app/configuration/routes.py`: routes, afstandsversies en transacties; geen oude kandidaten.
- `backend/app/configuration/web/routes.html` en `routes.js`: eenvoudige lijst en aanpasformulieren.
- `scripts/manage_transport.py`: standaard nieuw beheer, oud beheer uitsluitend met --legacy.
- `backend/tests/test_transport_routes.py`: fictieve tests en optionele controle van de nieuwe bron.
# Trein: kilometerafstand niet van toepassing

Treinroutes tonen overal `n.v.t.` voor de kilometerafstand, ook bij oude numerieke
bronafstanden. Toevoegen, aanpassen en verhuizen vereisen geen treinafstand.
Een ontbrekende treinafstand telt niet als na te kijken afstand. Fase 4 levert
`km_applicable: false` en `kms: null` voor treinroutes; deze zijn uitgesloten van
kilometervergoeding. Naam-, locatie- en ingangsdatumcontroles blijven gelden.
Historische bronwaarden blijven bewaard; ze worden niet als vergoedbare km gebruikt.
