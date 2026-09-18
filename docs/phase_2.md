# Fase 2 — Cleaning van een gekozen periode

## Uitvoeren in de VS Code-terminal

Vanuit de projectmap:

```bash
.venv/bin/python scripts/clean_planet.py "/Users/nielspeters/Downloads/Export kms 01.01.2026 - 31.08.2026.xlsx" --month 2026-08
.venv/bin/python -m pytest -q
```

De maand is `YYYY-MM`, niet alleen `augustus`: het jaar is noodzakelijk. Je kunt een andere maand kiezen zonder codewijziging. Alle maanden verwerken vereist bewust `--all-months`. Zonder periode stopt de CLI; beide opties tegelijk mogen niet.

## Wat gebeurt waar, in volgorde?

1. `scripts/clean_planet.py` leest je bronpad en periodekeuze. Het schrijft uitsluitend geaggregeerde tellingen naar de terminal.
2. `backend/app/importers/planet.py` valideert de volledige bron en verwijdert structurele summary-/lege/headerregels. Daarna selecteert de importer uitsluitend de gevraagde maand. Importfouten, ook buiten die maand, blokkeren cleaning: we accepteren geen stilzwijgend onvolledig resultaat. Het importscript toont de foutcodes.
3. `backend/app/cleaning/planet.py:clean_import` ontvangt alleen deze geselecteerde shiften en controleert dat geen rij buiten de maand is meegekomen.
4. Eerst worden alle shiften met Id `1112`, `1113`, `1114`, `1115`, `1116` uitgesloten als `GHOST_AGENT`: door de gebruiker bevestigd als ghost-agenten. Daarna wordt Remark `Telework` verwijderd via volledige-celvergelijking, ongevoelig voor hoofdletters en spaties aan de buitenkant. Geen substringfilter: `Telework extra` wordt niet blind verwijderd. De ghost-lijst staat centraal in `CleaningPolicy.ghost_employee_ids`.
5. Eventuele expliciet bevestigde extra uitsluitingen komen centraal uit `CleaningPolicy`. Standaard is die lijst leeg. Alle overige niet-lege opmerkingen blijven behouden als unresolved, ook `48h_ICTS_Extra_Shift`. Unresolved betekent dat hun businessbetekenis nog niet beslist is, niet dat de bronrij ongeldig is.
6. De resterende shiften worden gegroepeerd op `[Id, Day, fysieke locatie]`. Gebruikersbevestiging: `DELTA AIRLINES`, `HAINAN AIRLINES`, `LATAM CARGO` en `TUI` zijn één fysieke locatie `LUCHTHAVEN`. Hiervoor geldt een expliciete configureerbare mapping in `CleaningPolicy.location_aliases` (hoofdletterongevoelige volledige naam, buitenste spaties genegeerd). Voor dezelfde werknemer en dag blijft dus één luchthavenbeweging, ook met uren tussen de shiften. Andere Customers behouden hun exacte eigen sleutel; geen substring/fuzzy mapping of gok dat andere airlines ook dezelfde locatie zijn. Verschillende fysieke locaties, dagen en personeelsnummers blijven apart. De originele Customer wordt nooit overschreven. `Movement.physical_location` toont de gebruikte groepeerlocatie, niet een gekozen vervoersreferentie of tarief.
7. Elke `Movement` bewaart **alle** resterende oorspronkelijke `source_shifts`: tijden, opmerkingen, kilometers en bronrijen gaan niet verloren. `removals` geeft reden en bronshift; `unresolved_shifts` maakt de nog te beoordelen opmerkingen zichtbaar voor latere review. Er wordt geen dominante shift, tarief of afstand gekozen. Niet opnieuw kilometers optellen over deze bronshiften: dat is niet de betekenis van deduplicatie.

Dit resultaat leeft alleen in het geheugen. Nog geen dashboard, opslag, Excel-output of berekening.

## Augustuscontrole op de aangeleverde bron

| Telling | Aantal |
| --- | ---: |
| Bronrijen, volledige januari–augustusexport | 9.472 |
| Summaryregels, volledige bron | 0 |
| Geldige shiften buiten augustus | 8.066 |
| Ingelezen voor augustus-cleaning | 1.406 |
| Verwijderd als ghost-agent | 105 |
| Verwijderd als Telework | 13 |
| Bevestigde extra niet-relevante categorieën verwijderd | 0 |
| Dubbele bewegingen | 324 |
| Overgebleven bewegingen | 964 |

Cleaningcontrole inclusief ICTS: `1.406 = 105 + 13 + 0 + 324 + 964`. De luchthavenmapping voegt 92 dubbele bewegingen toe ten opzichte van de originele Customer. Summarytellingen blijven bronbreed en zijn al in fase 1 verwijderd.

De eerdere eenmalige augustus-reviewexport met 245 rijen is een historische snapshot van vóór de ghost- en luchthavenregels. Die bevat de 105 ghost-shiften en 91 extra luchthaven-dubbelen nog niet en is geen actuele volledige verwijderingslijst. Een nieuwe reviewexport moet alle regels gebruiken; de oude export wordt niet stilzwijgend overschreven.

De Remark-analyse toont Telework in de bron (173 rijen totaal, 13 in augustus). Andere waarden omvatten OV-codes, Wissel, Administration, extra-shiftcodes en vrije tekst. Er is geen HR-bevestiging dat die andere categorieën afwezigheden zijn; daarom geen gegokte verwijderingen. Vrije tekst/persoonsgegevens worden niet in documentatie opgeslagen.

## Configureerbare uitsluitingen

Locatiekoppelingen worden uit `config/locations.toml` geladen, met versie en optionele geldigheidsdatums. ICTS BELGIUM BVBA is nu handmatig bevestigd als vijfde luchthavenklant. Bron-Kms zijn onbetrouwbaar; geen gebruik voor locatieherkenning, suggesties of deduplicatie. Zie `location_review.md` om klanten handmatig toe te voegen.

Alleen na HR-bevestiging kun je bijvoorbeeld `--exclude-remark "BEVESTIGDE_CODE"` toevoegen; herhaal de optie voor meerdere codes. Dit is geen voorgedefinieerde echte code. De service bewaart de genormaliseerde gebruikte policy in het resultaat. De latere dashboardlaag kan dezelfde policy aanleveren, maar is nu niet gebouwd. Bewaar bij latere persistente runs ook bronhash, periode en policy; deze fase slaat niets op.

## Tests en afbakening

`backend/tests/test_planet_cleaning.py` gebruikt fictieve data voor filtering vóór deduplicatie, behoud van verschillende locaties, behoud van speciale opmerkingen/afstanden, configureerbare uitsluitingen, maandisolatie, foutblokkering en tellingen. Een optionele private augustuscontrole wordt ingeschakeld met `PLANET_SOURCE` zoals bij fase 1.

Volgende fase volgens het bronproject: **fase 3, vervoersreferentie-importer**. Geen koppeling of tarieven in fase 2.
