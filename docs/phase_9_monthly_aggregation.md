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
blokkeringen van één werknemer springen. `monthly.ready` betekent dat iedere
beweging rekenkundig berekend of terecht uitgesloten is. `payroll_ready` wordt
pas waar wanneer daarnaast iedere werknemer de hele maand één eenduidig extern
loonnummer heeft. De daaropvolgende officiële Accerta-export staat beschreven
in `docs/acerta_export.md` en maakt altijd een nieuw bestand.
