# HR Vervoerskosten

Dit project wordt gefaseerd opgebouwd om maandelijkse vervoersvergoedingen voor bewakingsagenten betrouwbaar, testbaar en traceerbaar te verwerken.

## Openen in VS Code

Open een terminal in de map die `hr-vervoerskosten` bevat en voer uit:

```bash
code hr-vervoerskosten
```

Of kies in VS Code `File` > `Open Folder...` en selecteer de map `hr-vervoerskosten`.

## Huidige status

**Nieuw ontwerp voor adresgebaseerde afstanden:** zie
`docs/automatic_distances_design.md`. De huidige uitvoering blijft intact;
Mapbox is nog niet gekoppeld en er worden geen werknemersadressen extern verwerkt.
De eerstvolgende bouwstap is een afzonderlijke lokale adresbasis met historie.

Fase 5: upload de maandelijkse Pl@net-export rechtstreeks in het dashboard. Alle
maanden worden verwerkt; gewone autoritten krijgen traceerbare controlebedragen.
Beheer gedateerde tarieven via **Instellingen · tarieven**. Speciale gevallen
blijven apart, nog geen definitieve uitbetalingen of Acerta-export.
Lees `docs/phase_5.md` voor de controlelijst en de nog open businessregels.

Fase 4 is toegevoegd: `scripts/match_planet.py SOURCE --month YYYY-MM` koppelt de behouden fase-2-bewegingen aan de actuele werknemers en routes. Augustus is al ingelezen. Bekijk Maandshiften · fase 4 in het dashboard; onzekere matches blijven zichtbaar en kunnen expliciet bevestigd worden. Zie `docs/phase_4.md`. Geen vergoedingberekening.

**Actueel fase-3-beheer:** de nieuwe opgeschoonde Sociaal-abo-Excel is de enige startbron. Het dashboard heeft één lijst met 62 werknemers en 143 routes, apart per locatie en vervoerswijze. Eén afstandsband blijft Nakijken. Toevoegen, afstand aanpassen, naam wijzigen en gedateerde verhuizingen blijven beschikbaar. Start met `.venv/bin/python scripts/manage_transport.py`; lees `docs/simple_transport.md`. De oudere kandidaatworkflow hieronder is historische context en staat apart achter `--legacy`.

Fase 0 bevat:

- de Python-projectbasis;
- pytest-configuratie;
- privacyregels voor bron- en outputbestanden;
- een privacybewust inspectiescript voor de aangeleverde bronnen;
- het gedocumenteerde datacontract in `docs/data_contract.md`.

Fase 1 voegt een geteste importer voor de rechtstreekse Pl@net-export toe, inclusief maandselectie, bronherkomst en zichtbare validatiemeldingen. De eerdere augustus-2025-export was al door HR aangepast en is alleen historische context.

Fase 2 voegt cleaning van de expliciet gekozen periode toe: ghost-agenten en Telework verwijderen, bevestigde extra uitsluitingen en groeperen op `[Id, Day, fysieke locatie]` met behoud van bronshiften. Delta, Hainan, Latam en TUI vormen volgens gebruikersbevestiging één luchthavenlocatie. Andere Customers blijven apart. Lees `docs/phase_2.md` voor de stappen en tellingen.

De cleaning-CLI laadt handmatige bevestigingen uit `config/locations.toml`, inclusief `ICTS BELGIUM BVBA` als luchthavenklant. Bronkilometers zijn onbetrouwbaar en worden niet gebruikt voor locatieherkenning, suggesties of deduplicatie. Lees `docs/location_review.md` om klanten handmatig met ingangsdatum toe te voegen.

Er is nog geen automatische matching, berekeningslogica of Excel-exporter. Fase 3 bevat nu lokaal vervoerbeheer met een dashboard en API. Lees `docs/phase_1.md` voor de importerwerking en `docs/configurable_rules.md` voor later aanpasbare businessregels.

Fase 3 gebruikt uit `Report` alleen naam, basislocatie, kilometers en vervoer. Speciale toeslaglocatieregels worden uitgesloten. De Excel is een eenmalige startbron; daarna beheer je werknemers, fysieke locaties, vervoerswijze en gedateerde afstandsversies in de lokale database. Verhuizen werkt alle bestaande locaties samen bij, zonder oude afstandsversies te overschrijven. Lees `docs/phase_3.md` en de stapsgewijze handleiding `docs/transport_management.md`.

```bash
.venv/bin/python scripts/manage_transport.py
```

Open daarna `http://127.0.0.1:8765`. Het dashboard is uitsluitend lokaal, niet geschikt voor publiek hosten. Sociaal abo heeft 70 werknemers en 104 volledige afstand-/vervoerinstellingen automatisch bevestigd; 66 uitzonderingsregels blijven zichtbaar op Nakijken. Alleen Planet-ID-koppelingen en onvolledige/conflicterende gegevens vereisen nog een keuze.

```bash
python scripts/import_reference.py "/pad/naar/VERVOER Sociaal abo vanaf 01.02.2026.xlsx"
```

## Lokale installatie

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Tests

```bash
pytest
```

VS Code herkent de pytest-configuratie automatisch. Selecteer zo nodig `.venv/bin/python` via `Python: Select Interpreter`.

## Fase-1-importer uitvoeren

```bash
python scripts/import_planet.py "/pad/naar/rechtstreekse-planet-export.xlsx"
python scripts/import_planet.py "/pad/naar/rechtstreekse-planet-export.xlsx" --month 2026-08
```

Zonder maandparameter blijven alle maanden behouden. Met maandparameter wordt één maand expliciet geselecteerd; geldige rijen buiten de selectie worden apart geteld. De CLI toont alleen geaggregeerde tellingen, geen HR-records, en schrijft geen outputbestanden. Meldingen gelden voor de volledige bron.

De normale `pytest`-run gebruikt fictieve data. De optionele private snapshotcontrole staat in `docs/phase_1.md`.

## Historische fase-0-broninspectie herhalen

Het script toont alleen structuur en geaggregeerde kwaliteitsmetingen. Het schrijft geen HR-records weg.

```bash
python scripts/inspect_sources.py \
  --performance "/pad/naar/Export kms.xlsx" \
  --reference "/pad/naar/VERVOER Sociaal abo.xlsx" \
  --acerta "/pad/naar/VERVOER afwijkende lonen.xlsx" \
  --pdf "/pad/naar/vervoerskosten.pdf"
```

## Privacy

- Plaats echte HR-bestanden nooit in Git.
- `data/input/` en `data/output/` zijn genegeerd, behalve hun `.gitkeep`-bestanden. `data/state/` en SQLite-bestanden/back-ups zijn eveneens genegeerd.
- Het inspectiescript toont geen namen, personeelsnummers of volledige bronrijen.
- Overschrijf nooit een bronbestand. Latere outputs horen als nieuw bestand in `data/output/`.
- Automatische tests gebruiken uitsluitend fictieve gegevens.

## Projectindeling

```text
backend/
  app/
    models/     Shift, importresultaat, meldingen en rapport
    importers/  Pl@net-importer, geen businessregels
  tests/        automatische tests met fictieve data
data/
  input/        lokale HR-bronnen, niet in Git
  output/       gegenereerde bestanden, niet in Git
docs/
  data_contract.md
  phase_1.md
  configurable_rules.md
scripts/
  inspect_sources.py
  import_planet.py
```

## Publiceren naar GitHub

De map is lokaal als Git-repository geïnitialiseerd met branch `main`. Maak eerst zelf een lege repository op GitHub en koppel die daarna:

```bash
git add .
git commit -m "Initial project setup and data contract"
git remote add origin git@github.com:JOUW-GEBRUIKERSNAAM/hr-vervoerskosten.git
git push -u origin main
```

Gebruik eventueel een HTTPS-URL in plaats van SSH. Controleer vóór iedere commit met `git status` dat er geen HR-bronbestanden zijn toegevoegd.
# Mapbox woonadressen

De eerste geocoderingstap is beschikbaar: lokale tokenconfiguratie en één
adres per klik, met expliciete resultaatcontrole. Zie
[token instellen en één adres testen](docs/mapbox_setup.md).
Er zijn geen routeafstanden of vergoedingen vervangen door deze uitbreiding.
