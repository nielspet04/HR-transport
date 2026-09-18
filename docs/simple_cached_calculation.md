# Eenvoudige auto: opgeslagen routeafstand koppelen aan het tarief

Maandshiften berekent voortaan de eenvoudige autoritten met de opgeslagen route
geldig voor werknemer, werklocatie, woonadres, locatieadres en prestatiedatum.
Een werknemer-specifieke HR-correctie heeft voorrang. Kilometers worden naar boven
afgerond. Geen nieuwe Mapbox-aanvragen en geen fallback naar Planet/Sociaal-abo-km.

Als een geldige Auto/Privé auto-optie ingesteld is, is auto de standaard, ook als
fiets of trein als alternatief ingesteld staat. Alleen fiets ingesteld maakt geen
autoroute aan. Meerdere autoroutes blijven geblokkeerd; trein-only is uitgesloten.
De toekomstige kalenderkeuze voor fiets is nog niet gebouwd.

De bestaande autotariefversie geldig op prestatiedatum wordt gebruikt: dagelijks
tabelbedrag tot 60 enkele km, daarna het ingestelde extra bedrag per km. Dit is
geen nieuw algemeen lineair km-tarief en er wordt niet automatisch maal twee gedaan.
Start tussen 22:00 en 06:00, 48h/speciale gevallen, bedrijfswagen en meerdere
werklocaties dezelfde dag worden niet uitbetaald in deze eenvoudige berekening.
Ontbrekende routes, coördinaten, koppelingen of tariefversies blokkeren bedragen.

De berekening is een actuele controleweergave: HR-correcties werken direct door
bij vernieuwen/herladen, evenals de huidige geldige configuratie. Oude opgeslagen
verwerkingen en providerresultaten worden niet overschreven. Verouderde koppelingen/
tarieven blokkeren de actuele berekening tot de shiften opnieuw zijn verwerkt.
Bronregel, gebruikte route-ID, afstandsbron, correctiereden en tarief blijven zichtbaar.
Eerder gedownloade Excel-bestanden veranderen niet. Dit is geen uitbetalingsbestand:
fietsselectie, tussenlocatietrajecten, speciale tarieven en weekmaximum volgen later.
