# HR-correctie van een Mapbox-afstand

Werknemersroutes → routes laden → werknemer openklikken → **Afstand corrigeren**.
Vul gehele enkele kilometers en een verplichte reden in. Auto en fiets zijn apart.
De correctie geldt voor deze werknemer en deze concrete adres-/locatie-/profielroute.
Ook als twee werknemers hetzelfde Mapbox-cache-resultaat delen, blijven hun
correcties onafhankelijk. Een verhuizing of andere locatieadrescombinatie erft de
correctie niet automatisch. Alleen bestaande READY-afstanden kunnen worden gecorrigeerd.

Dashboard en nieuwe Excel-exports gebruiken de HR-afstand en vermelden HR-correctie.
Mapbox-kilometers, coördinaten en kaartlijn blijven ongewijzigd bewaard.
De kaart toont dus geen door HR aangepaste route. Correcties gebruiken geen API.
**Mapbox-afstand herstellen** vraagt ook een reden en voegt een historielog toe;
niets wordt verwijderd. Eerder gedownloade Excel-bestanden veranderen niet.

Correcties staan blijvend in route_distance_corrections in de bestaande private
SQLite-database en vallen onder dezelfde databaseback-ups.
De Mapbox-afstanden en hun correcties vervangen nog niet de handmatige afstand
in de vergoeding-engine; deze wijziging betreft het automatische routeoverzicht
en de controle-export. De lokale app registreert reden en tijdstip, geen login-identiteit.
