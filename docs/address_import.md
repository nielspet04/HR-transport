# Stap 1: woonadressen aan bestaande profielen

De gebruiker bevestigde 1 januari 2026 als ingangsdatum voor deze adreslijst.
Deze datum is een HR-keuze, niet afgeleid uit de bestandsdatum.

`scripts/import_addresses.py` leest het werkblad Report, met Naam, Straat,
Nummer, Bus, Postcode en Gemeente. Het bronbestand wordt niet aangepast.
Formules, Excel-fouten en ontbrekende verplichte gegevens stoppen de import.

Naammatching gebruikt dezelfde normalisatie als de bestaande werknemerslijst:
Unicode-normalisatie, hoofdletterongevoelig en samengevouwen spaties. Alleen
één exacte naam met één bronregel wordt automatisch gekoppeld. Andere namen,
dubbele namen en werknemers die al een adres hebben blijven ter controle.
Er worden nooit werknemers aangemaakt door deze adresimport.

De nieuwe tabellen worker_addresses, address_imports en address_candidates
staan in dezelfde private routes.sqlite3-database. worker_id verwijst naar
het bestaande profiel. Bronhash en Excel-rijnummer blijven bewaard. Een
herhaalde import van hetzelfde bestand is idempotent. Andere importbestanden
overschrijven nooit bestaande woonadressen automatisch.

In Werknemers/routes staat Woonadressen. Kies een werknemer om het adres aan
te passen. Vul een ingangsdatum en reden in. Elke wijziging krijgt een nieuwe
versie, ook bij een correctie op dezelfde datum. De laatste versie op of vóór
de gekozen peildatum is actief. Het bestaande Historiek-vinkje toont alle
adresversies. Verhuizingen krijgen hun werkelijke ingangsdatum.

Bronregels ter controle kunnen aan een bestaand profiel worden gekoppeld of
met een reden genegeerd. Geen fuzzy automatische koppeling. Een nieuwe
werknemer moet eerst via het bestaande profielbeheer worden toegevoegd.

De bron bevat geen land. Geïmporteerde adressen houden daarom een lege
landcode. Handmatige adrescorrecties vragen een tweelettercode, bijvoorbeeld
BE of NL. Er is nog geen Mapbox-geocodering of tokenconfiguratie. Coördinaten
worden dus uitdrukkelijk als nog niet aangevraagd getoond, niet als nul.
Afstanden, tarieven en maandresultaten blijven ongewijzigd.

De CLI werkt standaard als controle zonder wijzigingen. Met --apply maakt
ze vóór schemawijziging/import een consistente, private SQLite-backup in
data/state/backups. Deze lokale backup is geen OneDrive-backup en bevat niet
de afzonderlijke Planet-uploads of config/locations.toml. Bescherm backups
zoals de originele HR-database. Adressen en databases horen niet op GitHub.

Op 18 september bevestigde de gebruiker dat iedereen in België woont. De
opgeslagen adressen met ontbrekend land kregen daarom een nieuwe versie met
BE op hun bestaande ingangsdatum. De vorige versies blijven bewaard. Ook
nog te koppelen adresbronregels kregen BE. Expliciete bestaande landcodes
worden nooit door deze bevestiging overschreven.

Volgende stap: Mapbox-token lokaal instellen, daarna de
bevestigde adressen geocoderen met permanente opslag. Routing en vervanging
van bestaande kilometerafstanden zijn afzonderlijke vervolgstappen.
