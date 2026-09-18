# Fysieke locaties handmatig bevestigen — fase 2

Nieuw gebruikersbesluit: Pl@net-`Kms` zijn onbetrouwbaar. Ze worden niet gebruikt voor locatieherkenning, suggesties of deduplicatie. Ze blijven alleen als onbetrouwbare bronwaarden bewaard; later niet gebruiken als gevalideerde berekeningsafstand. De kilometergebaseerde suggestielogica en CLI-optie zijn verwijderd.

## Bevestigde luchthavenklanten

`DELTA AIRLINES`, `HAINAN AIRLINES`, `LATAM CARGO`, `TUI`, `ICTS BELGIUM BVBA`: per werknemer/dag één luchthavenbeweging, ongeacht uren of bronkilometers. Originele Customers en shiften blijven bewaard. Andere Customers blijven apart totdat HR een gedeelde fysieke locatie bevestigt.

## Eenmalig toevoegen in VS Code

Open `config/locations.toml`, verhoog `version`, voeg na HR-bevestiging een blok toe. Fictief voorbeeld:

```toml
[[locations]]
customer = "FICTIEVE NIEUWE KLANT"
location = "LUCHTHAVEN"
valid_from = 2026-09-01
```

Gebruik de echte Customer en bevestigde ingangsdatum. TOML-datums zonder aanhalingstekens. Voor andere gedeelde fysieke locaties gebruik je bij hun klanten hetzelfde bevestigde locatie-label. Volledige naamvergelijking, hoofdletterongevoelig, buitenste spaties genegeerd; geen substring/fuzzy matching. Nieuwe spellingvarianten expliciet toevoegen.

De bestaande vijf koppelingen zijn algemeen bevestigd; geen historische ingangsdatum verzonnen. Bewaar historische regels: een verdwenen klant hoeft niet verwijderd te worden. Bij verhuizing sluit je de oude regel af met `valid_until` (inclusief) en voeg je een nieuwe toe vanaf de volgende dag. Overlappende periodes worden geweigerd.

## Opnieuw uitvoeren

```bash
.venv/bin/python scripts/clean_planet.py "/Users/nielspeters/Downloads/Export kms 01.01.2026 - 31.08.2026.xlsx" --month 2026-08
```

De CLI laadt standaard de TOML-configuratie. `--location-config` kan een bewaarde configuratieversie aanwijzen. Het resultaat bewaart de gebruikte regels/versie in het geheugen. Nog geen dashboard of persistente reviewhistoriek; latere opslag moet bronhash, maand en policy samen bewaren.

`backend/app/cleaning/locations.py` valideert handmatige gedateerde regels. `backend/tests/test_location_rules.py` controleert dat kilometers de groepering niet bepalen, en dat bevestigingen en datums herbruikbaar zijn. Klantnamen kunnen bedrijfsgevoelig zijn: controleer wat je deelt. De oude reviewexport is een historische snapshot, niet de actuele verwijderingslijst.
