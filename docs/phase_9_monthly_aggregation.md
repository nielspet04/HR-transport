# Fase 9 — maandtotalen per werknemer

`monthly_aggregation.aggregate` groepeert iedere behouden beweging uit de
geselecteerde maand per gekoppelde werknemer. Het resultaat bewaart tegelijk:

- werknemer en Planet-ID;
- berekend maandtotaal;
- aantallen per status;
- blokkeringstelling;
- elke detailshift met datum, locatie, vervoer, afstand, regel, reden en bedrag;
- of het bedrag automatisch berekend of door HR gecorrigeerd is.

Alleen `CALCULATED` telt financieel op. Trein, dienstwagen en mobiliteitsbudget
blijven als expliciet uitgesloten detailregels zichtbaar en tellen niet bij het
bedrag. `BLOCKED` en `LATER_PHASE` maken werknemer en maand niet afsluitbaar.
Een HR-bedragscorrectie telt met haar actieve bedrag mee; het oorspronkelijke
bedrag en de historie blijven in de berekeningsdetails aanwezig.

Het dashboard toont de maandtabel en kan rechtstreeks naar alle details of de
blokkeringen van één werknemer springen. `monthly.ready` betekent uitsluitend
dat iedere beweging rekenkundig berekend of terecht uitgesloten is. Het is nog
geen loonexport en zet `payroll_ready` niet op true: weekmaximum en eventuele
overige eindregels moeten eerst expliciet worden bevestigd. Fase 12 inspecteert
opnieuw het exacte Acerta-template en maakt altijd een nieuw bestand.
