# HR Vervoerskosten

Dit project wordt gefaseerd opgebouwd om maandelijkse vervoersvergoedingen voor bewakingsagenten betrouwbaar, testbaar en traceerbaar te verwerken.

## Openen in VS Code

Open een terminal in de map die `hr-vervoerskosten` bevat en voer uit:

```bash
code hr-vervoerskosten
```

Of kies in VS Code `File` > `Open Folder...` en selecteer de map `hr-vervoerskosten`.

## Huidige status

Fase 0 bevat uitsluitend:

- de Python-projectbasis;
- pytest-configuratie;
- privacyregels voor bron- en outputbestanden;
- een privacybewust inspectiescript voor de aangeleverde bronnen;
- het gedocumenteerde datacontract in `docs/data_contract.md`.

Er is nog geen importer, cleaning, matching, berekeningslogica, API, frontend of Excel-exporter.

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

## Broninspectie herhalen

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
- `data/input/` en `data/output/` zijn genegeerd, behalve hun `.gitkeep`-bestanden.
- Het inspectiescript toont geen namen, personeelsnummers of volledige bronrijen.
- Overschrijf nooit een bronbestand. Latere outputs horen als nieuw bestand in `data/output/`.
- Automatische tests gebruiken uitsluitend fictieve gegevens.

## Projectindeling

```text
backend/
  app/          Python-package; businesslagen volgen per fase
  tests/        automatische tests met fictieve data
data/
  input/        lokale HR-bronnen, niet in Git
  output/       gegenereerde bestanden, niet in Git
docs/
  data_contract.md
scripts/
  inspect_sources.py
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
