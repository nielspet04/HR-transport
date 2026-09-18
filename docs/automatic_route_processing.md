# Automatische coördinaten en routes

Automatische verwerking staat voor de huidige HR-database aan volgens het
expliciete gebruikersverzoek. Een nieuwe database staat uit totdat HR de
eenmalige toestemming activeert onder Instellingen → Automatische verwerking.

Na Planet-upload, koppeling, route-/werknemerwijziging en het opslaan van een
woonadres of locatieadres start een achtergrondtaak. Ook bij serverstart wordt
op ontbrekende resultaten gecontroleerd. De lokale token blijft op de server.
Alleen Belgische opgeslagen adressen worden verwerkt; onbekende adressen,
werknemerskoppelingen en vervoerswijzen worden niet geraden.

1. Permanente geocodering één keer per adres-hash. PENDING wordt vóór de API
   vastgelegd. Exacte/hoge matches met gematchte straat, huisnummer en postcode
   plus nauwkeurige coördinaten worden automatisch bevestigd. Onzekere matches
   blijven ter controle en worden niet gebruikt voor automatische routing.
2. Nieuwste shiftverwerkingen worden waar nodig vernieuwd. Alleen benodigde,
   gedateerde thuis→locatie- en locatie→locatie-profielen worden opgevraagd.
3. Elke afstand en geselecteerde routelijn blijft in route_distances /
   route_visualizations bewaard. Fiets gebruikt cycling, auto driving, geen traffic.
   Route-intentie wordt vooraf vastgelegd. READY, ERROR en PENDING worden nooit
   stilzwijgend opnieuw aangevraagd. Onderbroken jobs hervatten alleen ontbrekende
   intenties; een onzekere bestaande aanvraag vereist aparte opvolging.

Voortgang staat op Werknemersroutes; het dashboard ververst tijdens verwerking
automatisch, behalve terwijl een formulier wordt ingevuld. Instellingen bevat
een aan/uit-keuze en een knop voor verwerken van nog ontbrekende routes. Uit
zetten stopt na de huidige aanvraag, waarvan het resultaat wel wordt opgeslagen.
Jobs en status zijn lokaal in automatic_route_settings; routedata blijft apart.

## Afstanden tussen werklocaties

Werklocaties → Afstanden tussen werklocaties toont alle opgeslagen gerichte
trajecten en benodigde ontbrekende trajecten, per voertuig/profiel. De metadata
blijft bewaard in route_saved_contexts. De ruwe Mapbox-kilometers blijven
ongewijzigd; de getoonde/vergoede kilometers worden naar boven afgerond.

Een correctie hier geldt voor deze fysieke afstand/profiel bij alle werknemers.
Correcties staan append-only in location_transfer_corrections met reden en tijd.
Persoonlijke correcties blijven voorgaan. Herstellen voegt historie toe en
verwijdert niets. Dashboard, controleberekening en nieuwe Excel-export gebruiken
de effectieve HR-afstand. Een veranderd locatieadres creëert een nieuwe route;
oude route/correcties blijven bewaard. Geen nieuw Mapbox-verzoek voor correcties.

Shiftvolgorde moet zeker zijn; overlappende of ontbrekende tijden blijven apart.
De extra autorit gebruikt de standaardtabel en enkele tussenlocatie-km. Bike-only
routes worden berekend als cycling, maar fietsvergoeding/kalenderkeuze volgt later.
Weekmaximum en overige open uitzonderingen blijven buiten een payroll-export.
De SQLite-database bevat alle instellingen/resultaten; dezelfde back-upregels gelden.
