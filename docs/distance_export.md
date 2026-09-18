# Excelcontrole van werknemersafstanden

Herstart het dashboard, open Werknemersroutes, laad de benodigde routes en klik
**Excel exporteren · alle afstanden en shiften**.

- **Afstanden**: alle opgeslagen Mapbox-routes, inclusief historische adresversies,
  status, naam, locatie, vervoer en enkele kilometers. Geen eerdere Sociaal-abo-
  afstanden als automatische Mapbox-afstand presenteren.
- **Shiften**: alle maanden uit hetzelfde geselecteerde Planet-bestand, steeds de
  laatste verwerking per maand. Eén rij per fase-2-beweging en beschikbare
  vervoersoptie. Bronregels en samengevoegde shifttijden maken duplicaten traceerbaar,
  maar worden niet opnieuw als afzonderlijke verplaatsingen gerekend.

Bij meerdere vervoersopties staan deze apart met 'Vervoerskeuze controleren'.
Ontbrekende/geblokkeerde afstanden zijn leeg met status, nooit nul of een oude
handmatige afstand als stilzwijgende fallback. Trein en dienstwagen: n.v.t.
Export doet geen Mapbox-aanvragen en verandert geen koppelingen/adressen/afstanden.
Filters en vaste koppen ondersteunen controle. Dit is geen uitbetalingsbestand.

## Afronding

Alle operationele kilometers worden naar boven afgerond: 17,01 wordt 18;
17,00 blijft 17; nul blijft nul. Dit geldt voor dashboard, controlekaart, Excel
en de bestaande gewone-auto-berekening. Decimal wordt gebruikt, geen float-rounding.
De oorspronkelijke meters/kilometers en historische snapshots blijven ongewijzigd
opgeslagen voor audit. De afronding is een afgeleide waarde, geen nieuwe routeaanvraag.
Mapbox-afstanden vervangen nog niet de handmatige afstand in de vergoeding-engine.

## Terminal

`.venv/bin/python scripts/export_route_distances.py`

Optioneel `--run-id`, `--database`, `--output`. Bestaande bestanden worden niet
overschreven. Lokale uitvoer heeft rechten 0600 en outputs/ staat buiten Git.
Excel bevat persoonsgegevens: alleen delen met bevoegde HR-medewerkers.
