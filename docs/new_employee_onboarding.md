# Nieuwe werknemer uit een Pl@net-export

Een onbekende Pl@net-agent blijft zichtbaar in de volledigheidscontrole en kan
niet ongemerkt uit de berekening verdwijnen. Bij zo'n agent toont het dashboard
één onboardingformulier in `Maandshiften en berekeningen`.

Het formulier vult de bronnaam, reeds geïmporteerd extern loonnummer, bekende
fysieke werklocatie en standaard `Privé auto` vooraf in. HR vult het woonadres
en de geldigheidsdatum in en controleert de voorstellen. Een andere standaard
vervoerswijze kan meteen per locatie worden gekozen.

Na bevestiging worden in één database-transactie aangemaakt:

- het werknemersprofiel en de vaste Pl@net-ID-koppeling;
- het gedateerde woonadres;
- het reeds gevonden of handmatig ingevoerde externe loonnummer;
- de gedateerde vervoersinstelling en benodigde werknemer-locatieroute;
- eventueel nog ontbrekende klant-naar-fysieke-locatiekoppelingen;
- een nieuwe verwerking van alle maanden uit dezelfde bronexport.

Als één invoer of koppeling ongeldig is, wordt niets gedeeltelijk opgeslagen.
Wanneer automatische Mapbox-verwerking aanstaat, worden daarna coördinaten en
alleen de benodigde auto- of fietsroutes opgevraagd en blijvend opgeslagen.
