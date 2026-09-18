# Mapbox: eerste adres testen

Dit is alleen geocodering, nog geen routeafstand of gewijzigde vergoeding.

1. Open de projectterminal in VS Code.
2. Voer `.venv/bin/python scripts/setup_mapbox.py` uit.
3. Plak je token bij de verborgen invoer en druk Enter. De terminal toont geen
   tekens. Geef de token nooit als opdrachtargument, in chat of in broncode.
4. Stop je dashboard met Ctrl+C en start opnieuw met
   `.venv/bin/python scripts/manage_transport.py`.
5. Herlaad de pagina. Ga naar Werknemers/routes → Woonadressen →
   Mapbox · één adres testen.
6. Selecteer één adres. Controleer je bevoegdheid om het naar Mapbox te sturen,
   privacyvoorwaarden en dat permanente geocodering in je account beschikbaar
   is. Vink de bevestiging aan en klik Coördinaten voor dit adres opvragen.
7. Selecteer het adres opnieuw om het gevonden adres en de coördinaten te
   bekijken. De oorspronkelijke controleknoppen zijn op verzoek verwijderd;
   nieuwe resultaten blijven nog onbevestigd.

De token staat privé (600) in data/state/mapbox-token. Deze map is uitgesloten
van Git. Ze bevat het geheim in leesbare vorm: bescherm je computer en backups.
Alternatief: MAPBOX_ACCESS_TOKEN via de omgeving van het serverproces. Die
heeft voorrang op het bestand. De browser ziet alleen ingesteld/niet ingesteld.
Er is geen tokenveld of tokenwaarde in het dashboard of de SQLite-database.

Het verzoek gaat uitsluitend naar de Mapbox Geocoding v6 forward API met
permanent=true. Alleen straat, huisnummer, postcode, gemeente en BE worden
verstuurd, geen naam, werknemer-ID of shiften. Bus blijft lokaal; het punt is
het gebouw, niet de individuele woning in het gebouw. Geen automatisch
opvragen bij upload/start/refresh. Eén klik vraagt maximaal één adres op.
API-verkeer gebruikt een timeout van 15 seconden, geen redirects en geen
automatische retries. Kosten hangen af van je account en Mapbox-voorwaarden.

## Alle huidige adressen opvragen

Na een geslaagde test kun je in Woonadressen de sectie Alle ontbrekende
coördinaten opvragen gebruiken. Het plan toont het aantal nieuwe unieke
aanvragen voordat je toestemming geeft. Klik Alles opvragen en laat de
pagina open. Aanvragen lopen opeenvolgend, één per HTTP-verzoek en met een
eigen databasetransactie. Elke afgeronde aanvraag blijft meteen opgeslagen.
De voortgang en Stop na huidig adres blijven tijdens de verwerking zichtbaar.

Het plan gebruikt alleen de laatste effectieve adresversie per werknemer
vanaf vandaag. Historische/toekomstige adressen, adressen zonder BE en alle
opgeslagen resultaten worden overgeslagen, ook ERROR/NO_MATCH/REJECTED.
Identieke adrescomponenten delen één aanvraag. De server controleert per
aanvraag dat de adresversie nog actueel is. Wijzigingen in de configuratie
of een API-fout stoppen de bulk. NO_MATCH blijft zichtbaar en de bulk gaat
verder. Andere gegevens wijzigen tijdens de bulk is in deze pagina geblokkeerd.

Stoppen bewaart eerdere resultaten; opnieuw starten verwerkt alleen nog
ontbrekende aanvragen. Afsluiten/herladen stopt de browserlus; een lopende
serveraanvraag kan nog afronden. Vernieuw daarom eerst voordat je herstart.
Alle resultaten moeten nog expliciet gecontroleerd worden; geen automatische
bevestiging, kilometerberekening of routeaanvraag.

## Handmatige controle afgerond

Op verzoek van de gebruiker is de controle-interface verwijderd nadat alle
gevonden adresresultaten handmatig correct waren bevonden. Op 18 september
2026 zijn 65 resultaten bevestigd, naast 1 eerder bevestigd resultaat.
20 lagere provider-matchscores zijn expliciet door de gebruikerscontrole
overschreven; de originele matchmetadata is behouden. Eén NO_MATCH blijft
ontbrekend, want daarvoor zijn geen coördinaten beschikbaar. Vóór bevestiging
is een lokale SQLite-backup gemaakt. Er zijn geen nieuwe API-calls uitgevoerd.

De adreslijst en resultaatstatussen blijven zichtbaar, evenals adresbeheer en
het opvragen van ontbrekende coördinaten. Nieuwe/gecorrigeerde adressen worden
niet automatisch bevestigd. De backend houdt de controle- en auditregels voor
later gebruik; de knoppen/selectielijst zijn niet meer onderdeel van de UI.

Elk resultaat begint als REVIEW, ook bij een sterke match. Bevestigen kan
alleen bij een adresresultaat in België, geldige coördinaten, precieze
nauwkeurigheid, gematcht huisnummer/straat/postcode en exact/high confidence.
Een geïnterpoleerde of zwakke match blijft geblokkeerd; corrigeer het bronadres.
Menselijke controle garandeert niet dat de routetoegang het juiste hek is.

Resultaten staan in address_geocodes in de bestaande routes.sqlite3. Een
stabiele componenthash koppelt adresversies aan het resultaat; deze hash is
geen anonimisatie. Een identiek adres hergebruikt dezelfde aanvraag. Bij
verhuizing krijgt een veranderd adres een nieuwe sleutel, zonder oude
gegevens te verwijderen. Bevestigingsdatum en reden worden bewaard.

NO_MATCH en ERROR blijven zichtbaar en worden niet automatisch herhaald.
Zelfs een timeout kan al een betaalde aanvraag zijn. Deze eerste versie heeft
bewust nog geen retryknop. Los eerst de oorzaak op; een expliciete
retry met kostenwaarschuwing is een volgende uitbreiding. Geen 0,0 als fallback.

Bewaar routes.sqlite3 inclusief deze tabel in je bestaande backups. De token
valt niet onder SQLite-backups. Geen automatische OneDrive-backup ingesteld.
Deze lokale, single-user server mag niet publiek worden gehost.

Officiële API-documentatie: https://docs.mapbox.com/api/search/geocoding/
