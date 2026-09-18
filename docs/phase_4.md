# Fase 4 — werknemers en locaties koppelen aan maandshiften

## Resultaat

De maand wordt eerst expliciet gekozen, daarna door fase 2 opgeschoond en dan aan de actuele fase-3-routes gekoppeld. Eén resultaatrij is één behouden beweging uit fase 2 (agent + dag + fysieke locatie). Alle onderliggende bronshiften blijven met uren, bronklant, taak en rijnummer controleerbaar. Dit is geen kopie van alle oorspronkelijke exportregels: ghost-agenten en Telework zijn uitgesloten; dubbele bewegingen zijn gegroepeerd.

Het dashboard heeft twee tabbladen: Werknemers en routes, en Maandshiften · fase 4. De maandshiften zijn per agent en daarbinnen per locatie gegroepeerd. Kies één agent om zijn volledige overzicht open te zien. Beide vervoersroutes blijven bij één beweging beschikbaar zonder extra bewegingen aan te maken. Deze fase bepaalt niet welk vervoer werkelijk gebruikt is en berekent geen vergoeding.

## Een maand verwerken

```bash
.venv/bin/python scripts/match_planet.py "/pad/naar/clean-planet-export.xlsx" --month 2026-08
```

De nieuwe Sociaal-abo-basis moet al in `data/state/routes.sqlite3` staan. Gebruik desgewenst --db voor een andere lokale route-database. De bron wordt alleen gelezen; de verwerking wordt lokaal in de database opgeslagen. Er ontstaat geen publiek bestand of Git-artefact met HR-records.

Augustus 2026 is al verwerkt uit de aangeleverde clean export: 1.406 invoerrijen, 105 ghosts, 13 Telework, 324 extra dubbele bewegingen en 964 behouden bewegingen met 1.288 onderliggende bronshiften. Initieel 579 MATCHED, 252 UNMATCHED_LOCATION, 128 UNMATCHED_EMPLOYEE en 5 UNMATCHED_EMPLOYEE_LOCATION. Deze starttelling verandert na jouw expliciete bevestigingen. Er zijn 62 agenten in het resultaat, inclusief nog niet gekoppelde agenten; niets wordt wegens een ontbrekende match verborgen.

Stop de huidige dashboardserver met Ctrl+C en start opnieuw:

```bash
.venv/bin/python scripts/manage_transport.py
```

Herlaad `http://127.0.0.1:8765` en kies Maandshiften · fase 4. Alleen browserrefresh laadt geen nieuwe Python-code.

## Naammatching

1. Voeg Last name en First name samen; controleer ook de omgekeerde volgorde tegen de volledige referentienaam.
2. Normaliseer Unicode NFKC, hoofdletters en whitespace. Geen accent-, leesteken- of tokenverwijdering die verschillende personen gelijk zou maken.
3. Exact één genormaliseerde kandidaat wordt automatisch gekoppeld. Geen kandidaat is UNMATCHED_EMPLOYEE; meerdere kandidaten of verschillende namen bij één Planet-ID zijn AMBIGUOUS.
4. Twee verschillende Planet-IDs worden niet automatisch dezelfde referentiewerknemer. Dit vraagt expliciete ID-bevestigingen.
5. Spellinggelijkenissen leveren alleen suggesties, nooit automatische koppelingen. Kies zelf de juiste werknemer onder Naam- en locatiekoppelingen bevestigen.
6. Een bevestigde Planet-ID-koppeling blijft opgeslagen. De bevestigde bronnaam wordt bewaakt: een gewijzigde genormaliseerde naam geeft AMBIGUOUS, niet blind dezelfde persoon.

Id is niet gelijkgesteld aan een externe referentie. Externe referenties worden niet gebruikt.

## Locaties en routes

Fysieke airport-groepering blijft uit `config/locations.toml` komen. Hoofdletter-/spatievarianten van een fysieke locatienaam matchen exact tegen de routes. Andere labels, zoals ESA REDU tegenover Redu, moeten bewust gekoppeld worden. Kies de bronklant en bestaande fysieke referentielocatie; bewaar een reden. Het dashboard verwerkt de geselecteerde maand daarna opnieuw in één transactie.

Een bevestigde klantlocatie werkt ook vóór deduplicatie in fase 2: twee klanten die op dezelfde fysieke locatie liggen mogen geen extra bewegingen opleveren. Een conflict met bestaande TOML-regels blokkeert de bevestiging. Dashboardlocatiekoppelingen zijn ongedateerd en gelden bij volgende maandverwerkingen; gebruik gedateerde TOML-regels voor echte historische klantlocatieveranderingen.

Een naam- en locatiematch zonder route voor deze werknemer op deze locatie is UNMATCHED_EMPLOYEE_LOCATION. Voeg de correcte werknemerroute toe in fase 3 en verwerk de maand opnieuw. Een gekoppelde route zonder ingangsversie op de shiftdatum krijgt NO_EFFECTIVE_ROUTE: een toekomstige versie wordt nooit teruggeprojecteerd. Een onzekere referentieafstand blijft onzeker; Planet-Kms zijn nergens als afstand gebruikt.

## Controle en momentopnamen

MATCHED betekent alleen werknemer, locatie en route-identiteit gekoppeld, niet berekend of uitbetaald. De afzonderlijke werknemer- en locatiestatus blijven in de verwerking bewaard. De matching verwerkt alle bewegingen; de som van statustellingen moet gelijk zijn aan het aantal bewegingen.

Na bevestigen van een identiteit/klantlocatie wordt de geselecteerde maand direct opnieuw verwerkt. De bron moet nog op dezelfde plek staan en dezelfde hash hebben; anders blijft de bevestiging niet opgeslagen. Geen gedeeltelijk opgeslagen mapping met mislukte herverwerking.

Oude verwerkingen blijven momentopnamen. Als fase-3-gegevens of koppelingen wijzigen, krijgt een oudere verwerking een waarschuwing; geen stilzwijgend actueel resultaat claimen. Verwerk zo'n maand opnieuw met het script. Het dashboard laat per maand de nieuwste verwerking kiezen. Tarieven en vervoerkeuze per daadwerkelijke shift blijven voor volgende fasen.

## Waar zit de code?

- `backend/app/matching.py`: deterministische pure matching, expliciete fysieke policy, statussen en routeversies.
- `scripts/match_planet.py`: bron en maand kiezen, fases 1/2/4 uitvoeren, resultaat opslaan.
- `backend/app/configuration/routes.py`: bevestigde mappings, audit, maandmomentopnamen en atomaire herverwerking.
- `backend/app/configuration/web/routes.html` en `routes.js`: maand-/agentkeuze en detailoverzicht.
- `backend/tests/test_matching.py`: normalisatie, ambiguïteit, suggesties, geen routefan-out, effectieve datums, cleaningtellingen en rollback.
# Update: volledig bronbestand en werkende vernieuwknop

Fase 5 voegt dashboarduploads, gedateerde autotariefinstellingen en controlebedragen
toe. Zie `phase_5.md`; oudere opmerkingen hieronder over geen berekening beschrijven
uitsluitend de oorspronkelijke fase 4.

`scripts/match_planet.py BRONBESTAND` verwerkt nu alle maanden samen. De oudere
`--month`-optie controleert alleen of die maand bestaat; ze beperkt de verwerking
niet meer. Kies de gewenste maand in het dashboard.

De knop **Vernieuwen** verwerkt het volledige bronbestand van de geselecteerde
maand opnieuw en behoudt de maand- en agentselectie indien beschikbaar. Ook een
bevestigde naam- of locatiekoppeling verwerkt alle maanden uit die bron opnieuw.
Elke verwerking wordt volledig opgeslagen of volledig teruggedraaid bij fouten.
Oude momentopnamen blijven bewaard. Vernieuwen accepteert een gewijzigd geldig
bronbestand; bevestigen weigert een gewijzigde bron totdat opnieuw geïmporteerd is.
Agenten zonder match blijven zichtbaar; ghost-agenten en Telework blijven volgens
fase 2 uitgesloten. De maandselectie toont agenten met behouden shiften in die maand,
niet werknemers zonder shiften. Tarieven en vervoerskeuze worden niet berekend.

Onderstaande oudere maandgerichte instructies worden door deze update vervangen.
