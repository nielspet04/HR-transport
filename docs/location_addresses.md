# Adressen toevoegen aan bestaande locaties

Herstart het dashboard en ga naar Werknemers en routes. Bovenaan staat
Locaties · klantadressen. De lijst komt uit de bestaande werknemersroutes
en bevestigde klant-locatiekoppelingen, inclusief config/locations.toml.
Er is geen tweede klantenlijst en geen automatische nieuwe locatiematching.

1. Klik bij de gewenste locatie op Adres toevoegen (of Adres aanpassen).
2. Vul straat, huisnummer, eventueel bus, postcode, gemeente en landcode in.
   BE staat als aanpasbare standaard ingevuld; bevestig het juiste land.
3. Bevestig Geldig vanaf. De eerste invoer toont 1 januari 2026, in aansluiting
   op de gekozen woonadressenbasis. Wijzig dit als de locatie toen niet gold.
4. Vul een reden in en klik Locatieadres opslaan.

LUCHTHAVEN heeft één locatieadres dat alle reeds gekoppelde klanten delen.
PostNL Vilvoorde en Willebroek zijn afzonderlijke fysieke locaties. Dit
wijzigt geen klanten, klantkoppelingen, duplicaatregels, kilometers of tarieven.
Een ander fysiek toegangspunt kan later expliciet een aparte locatie vereisen.

De tabel toont de gekozen peildatum uit Situatie op datum. Historie tonen
toont alle opgeslagen adresversies. Een verhuizing krijgt de echte nieuwe
ingangsdatum. Een correctie op dezelfde datum voegt een versie toe en bewaart
de eerdere invoer; de laatst opgeslagen versie op die datum is actief.
Een versie vóór de laatst opgeslagen ingangsdatum wordt geweigerd.

Opslag: location_address_versions in dezelfde private routes.sqlite3. De
genormaliseerde bestaande locatienaam is de sleutel. Deze stap voegt geen
losse locatie-ID-registratie toe. Als een bestaande locatienaam later wordt
hernoemd, moet het adres expliciet meegekoppeld worden; namen niet stil wijzigen.
SQLite-backups bevatten ook deze tabel. Locatieadressen komen niet in Git.

## Locatiecoördinaten via Mapbox

Na het invullen kun je Mapbox · locatiecoördinaten opvragen gebruiken in
dezelfde sectie. Bevestig permanente geocodering en klik Locatiecoördinaten
opvragen. De bestaande lokale token wordt gebruikt; nooit een token in chat.
Laat de pagina open. Het plan toont alleen unieke, huidige Belgische adressen
zonder opgeslagen aanvraag. Oningevulde locaties worden overgeslagen, evenals
historische/toekomstige versies en reeds opgeslagen resultaten.

Elke aanvraag wordt apart opgeslagen in de bestaande address_geocodes-tabel.
Woonadres- en locatieadresversies kunnen dezelfde componenthash hergebruiken.
De locatie-ID komt uit location_address_versions; de tabel wordt niet verward
met worker_addresses. De server valideert per aanvraag de actuele versie.
Bij fout stopt de bulk; geen automatische retries. Een NO_MATCH blijft zichtbaar.

De locatietabel toont breedtegraad, lengtegraad, gevonden adres, nauwkeurigheid
en matchscore. Nieuwe resultaten blijven REVIEW, niet automatisch bevestigd.
Controleer vooral de juiste toegang bij luchthaven/cargo/grote sites: het
geocoderen van een straatadres bewijst niet dat de juiste poort gekozen is.
Een adreswijziging krijgt een nieuwe hash; eerdere resultaten blijven bestaan.

Dit vraagt geen routekilometers op en verandert geen vergoeding. De koppeling
agent + shiftlocatie + vervoerswijze en datumgebonden afstand is de vervolgstap.
