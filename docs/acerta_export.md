# Officiële Accerta-export

De afgesloten maand kan vanuit **Maandshiften → Maandtotalen per werknemer**
rechtstreeks worden geëxporteerd. Het officiële Accerta-sjabloon staat eenmalig
in de lokale gegevensmap. HR hoeft het bestand dus niet bij iedere maand te
uploaden. Elke download behoudt dezelfde tabbladen, headers, opmaak en interne
Accerta-metadata. De oorspronkelijke voorbeeldregels worden volledig vervangen
door de regels van de geselecteerde maand.

Een export wordt geweigerd wanneer de maand verouderd is, een beweging nog
blokkeert, een werknemer geen eenduidig loonnummer heeft, de looncode onbekend
is of de groepering niet op het maandtotaal aansluit.

Per werknemer worden betaalde bewegingen gegroepeerd op fysieke locatie,
looncode en exact bedrag per beweging:

- `25`: standaard autotarief;
- `26`: vroeg/laat;
- `4864`: 48u-extra-shift;
- `420`: fietsvergoeding.

`Eenheden` is het aantal bewegingen in de groep. `Bedrag per eenheid` is het
bedrag van één beweging. De loonperiode en startdatum zijn de eerste dag van de
geselecteerde maand; de einddatum is de laatste dag. Trein, dienstwagen en
mobiliteitsbudget en shifts die HR als telework markeert krijgen geen
exportregel.
