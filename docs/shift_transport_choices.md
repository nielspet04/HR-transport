# Vervoerskeuze per shift

De opgeslagen werknemer–locatieroute blijft de standaard. HR kan in het
maandoverzicht één concrete, behouden beweging overschrijven met privéauto,
fiets, trein, dienstwagen of mobiliteitsbudget. De sleutel bevat bronbestand, maand, werknemer, datum en
bronregels; een herverwerking van dezelfde export verliest de keuze niet.
Iedere wijziging is append-only opgeslagen in `shift_transport_choices` en
heeft een verplichte reden. `DEFAULT` herstelt de standaard zonder historie te
verwijderen.

De normale keuze zelf staat gedateerd in `transport_defaults`, per werknemer
én fysieke locatie. Het dashboard toont dit als **Standaard vervoersmiddel**;
de oude handmatige kilometerroute is niet langer de plek waar HR het normale
vervoer kiest. Beschikbare waarden zijn privéauto, fiets, trein, dienstwagen en
mobiliteitsbudget. Trein, dienstwagen en mobiliteitsbudget leveren standaard
geen kilometervergoeding op. Een individuele shiftkeuze gaat vóór deze
standaard, zonder hem voor andere dagen te wijzigen.

- Trein: zichtbaar, maar `EXCLUDED_TRAIN` en geen kilometervergoeding.
- Dienstwagen: zichtbaar als `EXCLUDED_COMPANY_CAR`, geen kilometervergoeding.
- Mobiliteitsbudget: zichtbaar als `EXCLUDED_MOBILITY_BUDGET`, geen kilometervergoeding.
- Auto: de gedateerde Mapbox-autoroute en gewone/vroeg-laat/48h-autoregels.
- Fiets: de gedateerde Mapbox-fietsroute, afstand naar boven afgerond,
  `enkele km × 2 × fietstarief`. Vroeg/laat en 48h worden nooit toegevoegd.

Het fietstarief is één gedateerde configuratiereeks in `bicycle_tariffs`.
De initiële versie is €0,37/km vanaf 2026-01-01 conform de projectbrief. Een
nieuwe dashboardversie vervangt eerdere periodes niet. Als een benodigde
auto- of fietsroute nog niet bestaat, neemt de bestaande automatische
routeverwerking ze eenmalig op en bewaart ze permanent onder de bevestigde
Mapbox-toestemming. Een ontbrekende route of ontbrekend tarief blokkeert de
berekening zichtbaar; er is geen fallback naar Planet- of Sociaal-abo-km.
