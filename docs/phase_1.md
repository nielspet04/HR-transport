# Fase 1 - Rechtstreekse Pl@net-importer

## Doel en grenzen

Excel -> getypeerde Shift-records. Geen cleaning, matching, bedragen, API, frontend of exporter. De door HR aangepaste augustus-2025-export is niet de productiebron. De nieuwe directe Pl@net-structuur is leidend.

## Bestanden en leesvolgorde

1. `backend/app/models/shift.py`: wat één record, melding en importresultaat bevat.
2. `backend/app/importers/planet.py`: read-only import en veldvalidatie.
3. `scripts/import_planet.py`: handmatig uitvoeren zonder persoonsgegevens te printen.
4. `backend/tests/test_planet_importer.py`: fictieve randgevallen.
5. `backend/tests/test_planet_local_source.py`: optionele private snapshotcontrole.

## Hoe de importer werkt

1. Controleer bestand en optionele maand (`YYYY-MM`).
2. Bereken SHA-256 en open Excel read-only; formules blijven herkenbaar. Er wordt nooit `save()` aangeroepen.
3. Zoek het werkblad `Total kms` en scan maximaal 75 rijen voor alle 11 kernheaders. Kolomvolgorde mag wijzigen; hoofdletters en overtollige headerspaties worden genormaliseerd. Ontbrekende of dubbele headers stoppen de import zichtbaar.
4. Verwerk iedere rij onder de header. Lege rijen, veilige `Total`-regels en herhaalde headers krijgen afzonderlijke tellers.
5. Valideer alle kernvelden. Rijfouten hebben een code, bronrij en veldnaam, maar bevatten geen foutieve bronwaarde of persoonsgegevens.
6. Bewaar een getypeerde Shift voor iedere geldige rij, inclusief de echte bronrij. Geen deduplicatie of verwijdering van opmerkingen.
7. Rapporteer kloktijdproblemen zonder algemene einddatum te gokken. `24:00` aan het einde wordt expliciet genormaliseerd met dagoffset +1.
8. Selecteer alleen bij een expliciete maandparameter de gewenste maand. Alle geldige bronmaanden blijven in het rapport zichtbaar. Rijfouten en waarschuwingen gelden voor de volledige bron, ook buiten de selectie.
9. Geef `ImportResult(shifts, issues, report)` terug. De CLI toont alleen tellingen. Er wordt geen HR-JSON of outputbestand opgeslagen.

## Shift-velden

| Bron | Modelveld | Type / afspraak |
| --- | --- | --- |
| Id | employee_id | Verplichte tekst; voorloopnullen behouden. Numerieke ID's worden niet gegokt of gepad. |
| Last name | last_name | Verplichte tekst |
| First name | first_name | Verplichte tekst |
| Department | department | Optionele tekst; leeg wordt None |
| Day | day | Python date; strikt YYYY-MM-DD of native Excel-datum |
| Task | task | Verplichte tekst |
| Debut tache | start_time | Python time; HH:MM, eventueel seconden of native Excel-tijd |
| Fin tache | end_time | Python time; expliciet 24:00 wordt 00:00 |
| Fin tache | end_time_day_offset | 1 bij expliciet 24:00; anders None (bron noemt geen offset) |
| Remark | remark | Optionele tekst, onbekende codes behouden |
| Customer | customer | Verplichte tekst; geen locatie-/matchingnormalisatie |
| Kms | kms | Decimal of None; een ontbrekende bronafstand wordt nooit nul |
| Bronmetadata | source_file / source_sheet / source_row | Herkomst, zonder data opnieuw te exporteren |

Tekst wordt alleen aan de randen getrimd; namen en locaties behouden hun casing en interne tekst. Kms ondersteunt getallen en eenvoudige decimale tekst met punt of komma, geen duizenden-/valutascheiding. Een negatieve bronwaarde wordt behouden met waarschuwing, niet als vergoeding geïnterpreteerd. Een formule of Excel-fout in een kernveld wordt afgewezen. Extra benoemde kolommen worden met waarschuwing genegeerd; niet-lege data onder een lege extra header wordt afgewezen.

Een `Total`-marker is alleen een samenvatting als alle kernvelden behalve Id en Kms leeg zijn. Een rij met zo'n marker en shiftdata is `AMBIGUOUS_SUMMARY_ROW`, zodat geen echte prestatie stilzwijgend verdwijnt.

## Tellers en fouten

```text
data_rows_seen = blank_rows + summary_rows + repeated_header_rows
                 + rejected_rows + imported_rows + outside_month_rows
```

Deze formule geldt voor iedere geslaagde structurele import. Een afgewezen rij kan meerdere meldingen hebben. Controleer dus de rijteller, niet het aantal errors, voor reconciliatie.

- `MISSING_VALUE`, `INVALID_DATE`, `INVALID_TIME`, `INVALID_KMS`, `INVALID_TEXT_TYPE`, `INVALID_IDENTIFIER_TYPE`: rijfout.
- `FORMULA_NOT_SUPPORTED`, `SOURCE_CELL_ERROR`, `DATE_CONTAINS_TIME`: rijfout, geen fallback.
- `AMBIGUOUS_SUMMARY_ROW`, `UNHEADED_DATA`: rijfout.
- `END_BEFORE_START`, `SAME_START_END_TIME`: kloktijdwaarschuwing; shift blijft behouden.
- `MISSING_KMS`, `NEGATIVE_KMS`: bronafstandswaarschuwing; shift blijft behouden.
- `EXPLICIT_24H_END`: informatie over expliciete bronnotatie.
- `MULTIPLE_MONTHS`: waarschuwing bij een bron met meerdere maanden, ook na maandselectie.
- `MONTH_NOT_PRESENT`: expliciete selectie zonder passende geldige bronrijen.
- CLI exitcode 0: geen errors; 1: zichtbare importerrors; 2: bestand/structuur/argument fout.

Geen berekening mag later onbewust een gedeeltelijk resultaat gebruiken: `result.has_errors` en de meldingen moeten eerst worden behandeld. Geldige rijen blijven beschikbaar om de fouten te kunnen onderzoeken.

## Handmatig testen vanuit de projectmap

```bash
source .venv/bin/activate
pytest

python scripts/import_planet.py "/Users/nielspeters/Downloads/Export kms 01.01.2026 - 31.08.2026.xlsx"

python scripts/import_planet.py "/Users/nielspeters/Downloads/Export kms 01.01.2026 - 31.08.2026.xlsx" --month 2026-08
```

Verwacht zonder selectie: 9.472 shifts, nul afgewezen, nul samenvattingen, acht maanden. Verwacht augustus: 1.406 shifts en 8.066 geldige rijen buiten de selectie.

Meldingen over de hele bron: 715 `END_BEFORE_START`, vier `EXPLICIT_24H_END` en één `MULTIPLE_MONTHS`. Het ontbreken van Department op 738 rijen is toegestaan. Nog geen vergoedingen berekend.

De gewone tests zijn volledig fictief en maken alleen tijdelijke minimale OOXML-bestanden. Voor de optionele controle op de private snapshot:

```bash
PLANET_SOURCE="/Users/nielspeters/Downloads/Export kms 01.01.2026 - 31.08.2026.xlsx" pytest backend/tests/test_planet_local_source.py
```

Deze snapshotcontrole vergelijkt kernvelden van alle 9.472 rijen, maandtellingen en hashes zonder persoonswaarden te tonen. Zonder PLANET_SOURCE wordt hij bewust overgeslagen. Hij geldt specifiek voor de aangeleverde snapshot, niet voor willekeurige toekomstige maandbestanden.

## Volgende fase

Fase 2: eerst de echte opmerkingen analyseren en cleaningregels expliciet vastleggen. Daarna telewerk en bevestigde niet-relevante categorieën verwerken, en deduplicatie volgens [Id, Day, Customer] testen. Geen tarieven.
