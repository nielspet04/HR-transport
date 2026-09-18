# Ontwerp — automatische afstanden, naast de bestaande berekening

## Update: routingopslag geblokkeerd onder standaardvoorwaarden

Latere gebruikersbevestiging: de gebruiker meldt toestemming te hebben voor
eenmalige routeaanvragen en permanente opslag. Op die verklaarde toestemming
is de vaste routeafstandstabel nu gebouwd; zie [routeafstanden](route_distances.md).
De standaardvoorwaarden hieronder blijven de reden waarom die aanvullende
toestemming nodig was. Er is geen contract namens de gebruiker afgesloten.

Op 18 september 2026 is de actuele officiële Product Terms-PDF van 21 juli
2026 rechtstreeks gecontroleerd. Sectie 2.10.1 op pagina 8 verbiedt export,
download, caching en opslag van Navigation API-resultaten. Directions valt
onder Navigation APIs. Een standaardaccount met Permanent Geocoding geeft
dus geen bevestigde toestemming om routeafstanden één keer op te vragen en
blijvend te bewaren. Dit ontwerp mag niet met zo'n Mapbox-cache worden
geactiveerd zonder passende schriftelijke contractuele toestemming.

Officiële bron: https://www.mapbox.com/legal/product-terms

De oorspronkelijke ontwerpstatus hieronder is historisch. Inmiddels zijn
woon- en locatieadressen en permanente geocodes geïmplementeerd en lokaal
opgeslagen. Er is nog geen Directions-aanvraag of routeafstandscache uitgevoerd.
De gebruikerswens blijft: alleen routes uit de export, datumgebonden adresversies,
auto/fiets apart, gerichte route en hergebruik zonder historische overschrijving.
Hiervoor is nu een expliciete keuze nodig: passend Mapbox-contract of een
routingprovider met passende opslagrechten. Bestaande gegevens blijven intact.

Status: ontwerp, 18/09/2026. Geen Mapbox-koppeling actief, geen adresimport
uitgevoerd en geen bestaande instellingen/database vervangen. Een aangemaakt
Mapbox-account is niet automatisch toestemming voor het extern verwerken van
werknemersadressen of het permanent bewaren van routingresultaten.

## Doel en maandelijkse werkwijze

HR uploadt de rechtstreekse Planet-export. De bestaande importer en ghost- /
Teleworkregels blijven behouden. Nieuwe agenten worden zichtbaar als **Adres
nodig**, niet stilzwijgend verwijderd. HR vult één woonadres in met ingangsdatum
en bevestigt de vervoerswijze per locatie. Nieuwe fysieke locaties krijgen één
bevestigd locatieadres/toegangspunt. Alleen daadwerkelijk benodigde routes
worden opgevraagd. Bestaande geldige afstanden worden hergebruikt, voor zover
de providercontracten die opslag toestaan.

Routing levert afstand, geen vergoeding. Tarieftabel, startuurregel, trein-
uitsluiting en overige vergoedingregels blijven afzonderlijk en gedateerd.
Een Mapbox-afstand is een berekende route, geen bewijs van een feitelijk gereden
traject. Een speciale afstandstariefregel wordt niet door Mapbox bepaald.

## Aansluiting van de aangeleverde bronnen

De afstandsspecificatie is bronmateriaal voor dit ontwerp. De unieke combinatie
agent/locatie wordt uitgebreid met adresversies, richting en vervoer; een upsert
die historische afstanden overschrijft wordt niet overgenomen.

De adreslijst heeft werkblad `Report`, header op rij 1, bereik A1:F70:
`Naam`, `Straat`, `Nummer`, `Bus`, `Postcode`, `Gemeente`. Er is geen agent-ID
of landkolom. Daarom koppelen we niet op rijnummer en verzinnen we geen Planet-ID.
Alleen een eenduidige genormaliseerde naammatch met een bestaande werknemer
mag als kandidaat dienen; ambiguïteit vereist HR-bevestiging. Bestaande bevestigde
Planet-ID-koppelingen blijven de brug naar de werknemer. Nieuwe agenten krijgen
een eigen interne sleutel en een bron-ID-binding met naamwijzigingscontrole.

Bus is optioneel; postcode/huisnummer/bus blijven tekst. Land moet worden
vastgelegd, niet blind uit de gemeente afgeleid. Geocoding moet een werkelijk
adres opleveren; een gevonden gemeentecentrum is geen voldoende resultaat.
Een import mag handmatige adreswijzigingen niet vervangen. Adreslijstdatum is
geen bewezen ingangsdatum voor alle historische woonadressen.

## Gegevensmodel (voorstel, nog niet gemigreerd)

| Object | Sleutel / inhoud |
| --- | --- |
| Agent | Stabiele interne ID, bestaande bevestigde Planet-ID-binding |
| Woonadresversie | Agent-ID, geldig vanaf, adresvelden, land, normalisatieversie |
| Fysieke locatie | Stabiele locatie-ID, klant-/taakaliases; één klant kan meerdere locaties hebben |
| Locatieadresversie | Locatie-ID, geldig vanaf, adres en bevestigd toegangspunt |
| Geocode | Adresversie, provider, coördinaten, controlestatus, datum, opslagrecht |
| Routeafstand | Gerichte oorsprong/bestemming-adresversies, auto/fietsprofiel, provider/beleidsversie, meters, datum, status, opslagrecht |
| HR-afstandscorrectie | Afstand, relevante combinatie, geldig vanaf, reden, oorspronkelijke berekening blijft bewaard |
| Verplaatsingskeuze | Agent/dag/bronshiften, vanuit thuis of rechtstreeks tussen locaties, bevestiging |
| Berekeningsmomentopname | Gebruikte adres-/afstand-/tariefversies, bronrijen, bedrag, uitleg, open punten |

Er is één herbruikbare actieve afstand per concrete routecontext; historische
versies worden niet verwijderd. Een genormaliseerde adresvingerafdruk is geen
anonimisering. Gebruik een versieerbare stabiele digest, niet Python `hash()`.
Herberekening bij verhuizen gebeurt alleen voor routes die vanaf de nieuwe
ingangsdatum nodig zijn. Augustus blijft bij het augustusadres. Een route van
A naar B wordt niet automatisch gebruikt voor B naar A.

De routingprovider kan wegen wijzigen: we bewaren wanneer en met welk beleid
een afstand berekend is. Verversen van routes wordt een expliciete controleactie,
geen stille wijziging van afgehandelde maanden. Afronding van route-meters naar
de kilometerband van de vergoeding is een afzonderlijke, nog te bevestigen regel.

## Klant-naar-klantverplaatsingen

Bronshiften blijven behouden. Een bevestigd dagtraject kan zijn:
`thuis → locatie A → locatie B`. De tweede verplaatsing gebruikt de opgeslagen
gerichte afstand A→B in plaats van nogmaals thuis→B; beide niet cumuleren.
Een ontbrekende tussenafstand blokkeert die vergoeding. Tijdvolgorde maakt een
voorstel maar bewijst geen rechtstreeks traject. Overlap, nachtgrenzen en
onderbrekingen vereisen controle. Retourritten worden niet automatisch toegevoegd.
Tarief voor klant→klant en 48h blijft unresolved tot HR dit bevestigt.

## Architectuur en providerkeuze

```text
Planet-import → bestaande cleaning → agent en fysieke locatie
                                          ↓
                          datum + adresversies + vervoerswijze
                                          ↓
                            onafhankelijke DistanceService
                               ↙                  ↘
                      lokale toegestane opslag   provideradapter
                                          ↓
                          afstand + status + herkomst
                                          ↓
                         bestaande vergoeding-engine
```

Geocoding (adres→coördinaten) staat los van routing (coördinaten→routeafstand).
Auto en fiets zijn aparte profielen. Eerst per unieke benodigde route dedupliceren,
daarna aanvragen plannen; niet alle werknemers met alle locaties combineren.
Rate limits, time-outs, begrensde retries, dubbele-importcontrole en een lokaal
aanvraagbudget voorkomen requestlussen. Een API-fout geeft geen nul kilometer.
Een provider mag verwisseld kunnen worden zonder tariefregels te herschrijven.

Mapbox-token uitsluitend server-side via een lokale omgevingsvariabele, niet in
Git, database, browser of logs. Geen token in chat vragen. Een interactieve kaart
is geen voorwaarde om routes te berekenen. Namen, agent-ID's, rijksregisternummers
en shiftroosters worden niet aan de provider meegestuurd.

## Opslagrechten, privacy en back-up

Voor de externe proef bevestigt HR/IT de toegestane verwerking van adressen en
coördinaten, inclusief bewaartermijnen en toegangsrechten. De Mapbox-documentatie
staat opslag van Permanent Geocoding-resultaten toe, niet van Temporary-resultaten.
Dit bevestigt niet het permanent bewaren van Directions/Matrix-routeafstanden.
We starten zo'n cache pas met bevestigde toepasselijke opslagrechten. Als die
ontbreken, kiezen we een passend contract/provider of een afzonderlijk ontworpen
werkwijze zonder verboden cache; geen stille omweg.

De eerdere circa-$0,50-inschatting voor 100 geocodingaanvragen is uitsluitend een
raming op basis van gepubliceerde gebruiksprijzen. Geen contract of definitieve
totaalprijs is bevestigd.

Voor de overstap maken we een consistente, geteste databaseback-up plus kopieën
van bronuploads en locatieregels, met een herstelcontrole. Een Git-branch alleen
bewaart geen genegeerde HR-database. De proef gebruikt een aparte database en
een expliciete modus; geen automatische terugval op het oude systeem. Het oude
systeem blijft beschikbaar ter vergelijking/herstel, niet als verborgen fallback.
Geen back-up uitgevoerd door dit ontwerp. OneDrive-bestemmingspad ontbreekt nog.

## Dashboardvoorstel

- **Agenten en adressen:** bestaand adres, datum, toevoegen, verhuizen, naamkoppeling.
- **Locaties:** klant/taakalias, adres, toegangspunt, shared-airportlocatie behouden.
- **Afstanden:** alleen gebruikte routes, auto/fiets, geocodingstatus, routeafstand,
  datum, herkomst, correctie met reden.
- **Maandcontrole:** bronshiften, oorsprong→bestemming, afstands-/tariefversie,
  bedrag of duidelijke blokkering; dagtraject expliciet bevestigen.
- **Instellingen:** gedateerde tarieven, bevestigd afrondingsbeleid, aanvraagbudget,
  providerstatus zonder token te tonen.

## Kleine uitvoeringsstappen en acceptatie

1. **Lokale adresbasis:** aparte proefdatabase, importer voor adreslijst, kandidaten
   naar agent-ID's, HR-adresbeheer met ingangsdatum. Geen externe aanvragen of
   wijzigingen aan productie. Test dubbele namen, ontbrekende adressen, herimport,
   nieuwe agent en historische verhuizing. Dit is de eerstvolgende bouwstap.
2. **Locaties en aanvragenplan:** stabiele sites/aliases, bevestigd toegangspunt,
   uniek plan voor alleen ontbrekende noodzakelijke profielen. Test shared site,
   nieuwe klant, ontbrekende locatie en geen onnodige combinaties.
3. **Mapbox-proef:** eerst fictieve/openbare adressen, dan uitsluitend na privacy-
   en opslagbevestiging echte gegevens. Token lokaal configureren. Test mislukte
   geocoding, twijfelachtig adres, geen route, time-out, budget en geen dataleklogs.
4. **Vergelijking:** oud versus nieuw op dezelfde maand; afstandsverschillen zijn
   zichtbaar, nooit automatisch als HR-goedkeuring behandeld. Afronding bevestigen.
5. **Dagtrajecten en berekening:** bevestigde A→B-keuzes, passend bevestigd tarief,
   traceerbare bedragen; geen dubbele thuisvergoeding.
6. **Overstap:** back-up en hersteltest, HR-controle, expliciet gekozen nieuwe modus.

Geen van stappen 1–6 is al geïmplementeerd door dit document. De huidige fase-5-
engine blijft ongewijzigd; fase 6 is nog niet gebouwd. Open beslissingen: permanent
routingopslagrecht, privacytoestemming, land/ingangsdatum startadressen, kilometer-
afronding, klant→klanttarief, 48h-tarief en OneDrive-back-uppad.

Referenties: aangeleverde `planet_distance_calculation_specification.md`,
adreslijststructuur en bestaande projectfases; actuele accountvoorwaarden nog
afzonderlijk te bevestigen. Mapbox-documentatie:
[Geocoding](https://docs.mapbox.com/api/search/geocoding/),
[Directions](https://docs.mapbox.com/api/navigation/directions/),
[Productvoorwaarden](https://www.mapbox.com/legal/product-terms).
