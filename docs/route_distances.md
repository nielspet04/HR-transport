# Vaste routeafstanden uit de export

De gebruiker bevestigde verkregen toestemming voor één Mapbox-aanvraag en
blijvende opslag van routeafstanden. Die bevestiging is als permission_basis
bij elke aanvraag opgenomen. Dit is geen zelfstandig door de applicatie
gecontroleerd Mapbox-contract; bewaar de toestemming ook bij HR/IT.

## Dashboard

1. Herstart de server en herlaad het dashboard.
2. Ga naar Werknemersroutes → Vaste routeafstanden · Mapbox.
3. Kies een exportverwerking en klik Benodigde routes bekijken.
4. Het plan neemt alle maanden uit dezelfde bronhash mee. Bij gewijzigde
   werknemer-/locatiekoppelingen of tarieven: eerst Maandshiften → Vernieuwen.
5. Controleer het aantal aanvragen en open Ontbrekende gegevens indien nodig.
6. Bevestig toestemming en klik Ontbrekende afstanden opvragen. Laat de pagina
   open. Stop na huidige route bewaart alle eerder afgeronde aanvragen.

## Selectie en routes

Alleen behouden bewegingen uit fase 2/4 worden gepland. Ghosts en Telework
komen niet terug. De gekoppelde werknemer en fysieke locatie zijn bepalend,
nooit Planet Kms. Per dag worden de dan geldige woon- en locatieadresversies
gebruikt. Geen fallback naar een toekomstig adres of handmatige oude afstand.
Wooncoördinaten moeten bevestigd zijn. Voor locatiecoördinaten gebruiken we
de beschikbare REVIEW/CONFIRMED-resultaten op basis van de eerdere verklaring
van de gebruiker dat de locatiepunten perfect gematcht zijn. Afgewezen,
ontbrekende, mislukte of ongeldige punten zijn geblokkeerd. Nieuwe locatiepunten
blijven aandacht vragen: het juiste gebouw is niet automatisch de juiste poort.

Auto en Privé auto → mapbox/driving; Fiets → mapbox/cycling. Als een werknemer
voor dezelfde locatie zowel fiets als auto geconfigureerd heeft, worden beide
afstandsalternatieven voorbereid. Dit beslist nog niet wat op een concrete
shift is gebruikt. Trein en Dienstwagen worden uitgesloten; andere onbekende
vervoerswijzen zijn zichtbaar geblokkeerd. Geen volledige agent×locatie-matrix.

Het verzoek is één gericht traject thuis → locatie, niet automatisch retour.
Er is geen driving-traffic, vertrekdatum of live verkeersinformatie. Met
alternatives=true worden de aangeboden alternatieven in dezelfde aanvraag
opgevraagd. We bewaren de kleinste geldige routeafstand in meters en exact
gedeeld door 1000 als Decimal-kilometers, zonder vergoedingafronding.
Dit is de kortste aangeboden route, niet gegarandeerd de wereldwijd kortste
rijbare weg. Er worden geen namen, IDs of shiften naar Mapbox gestuurd.

## Opslag en reproduceerbaarheid

route_distances staat in dezelfde private routes.sqlite3 en valt onder
SQLite-backups. De unieke sleutel bevat oorsprong/bestemming-adreshashes,
geocode-IDs, profiel, richting en routingbeleid. Een identieke combinatie
wordt ook over meerdere shiften/maanden/werknemers hergebruikt. De lijst toont
die waarde per relevante agent/locatie/vervoer en de gebruikte adresdatums.

Vóór de externe call wordt PENDING gecommit. READY bewaart het resultaat,
datum, beleid en aantal aangeboden routes. ERROR bewaart een veilige fout.
PENDING/ERROR krijgen geen automatische retry, ook niet na herstart of timeout:
de provider kan de oorspronkelijke aanvraag al verwerkt hebben. Een harde
onderbreking kan dus handmatige opvolging vereisen, nooit stil nog een call.
De cache rij wordt nooit overschreven door een herhaalde upload of aanvraag.
Een gewijzigde concrete adrescombinatie krijgt een nieuwe sleutel; de oude
afstand blijft voor historische context bewaard. Tussen aanvragen wacht de UI
250 ms; aanvragen zijn sequentieel en de bulk stopt bij een fout.

De database bepaalt de reproduceerbaarheid, niet herhaalde API-uitkomsten.
Mapbox kan zijn wegen of berekeningsalgoritme wijzigen. Geen stille refresh.

## Grenzen van deze stap

De bestaande route-kilometers, tarifering en maandmomentopnames zijn intact.
De nieuwe afstandstabel wordt nog niet automatisch in de vergoeding-engine
ingevuld. Eerst de routeaanvragen en afstanden controleren, daarna expliciete
overstap inclusief kilometerafronding. Klant→klant, retour, transportkeuze per
shift, bijzondere tarieven en het definitieve uitbetalingsbestand zijn niet
door deze stap geïmplementeerd.

Officiële API-documentatie: https://docs.mapbox.com/api/navigation/directions/
# Route controleren op de kaart

Bij een opgeslagen afstand verschijnt **Route bekijken** in Werknemersroutes.
Voor oude afstanden zonder geometrie vraagt **Routelijn éénmalig opvragen** één
aanvullende Directions-response op, volgens de expliciete toestemming van de gebruiker.
De intentie wordt vóór de aanvraag opgeslagen; ERROR en PENDING worden niet automatisch
herhaald. De nieuwe routelijn is een huidige controle, niet een reconstructie van de
oorspronkelijke aanvraag. De oorspronkelijke kilometers blijven altijd ongewijzigd.
Eventuele verschillen staan naast de kaart. Nieuwe afstandsaanvragen bewaren de
geometrie van precies de geselecteerde kortste aangeboden route meteen mee.

De kaart gebruikt een Mapbox Streets Static Images-achtergrond via de lokale server.
Elke weergave vraagt een kaartafbeelding op (afzonderlijk Mapbox-product/quotum),
maar geen nieuwe Directions-route. Token blijft server-side. Logo en attributie blijven
op de kaartafbeelding staan; achtergrond wordt niet blijvend opgeslagen.
De token moet kaartafbeeldingen toestaan (`styles:tiles`). Een ontbrekende achtergrond
wordt gemeld; de opgeslagen routelijn blijft beschikbaar. Achtergrond kan veranderen,
de bewaarde lijn en kilometers niet. De kaart is een overzicht, zonder zoom/pan.
