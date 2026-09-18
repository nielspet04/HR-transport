# Vervoerbeheer — stappen in VS Code

**Historische handleiding:** het nieuwe standaardbeheer is eenvoudiger en gebruikt uitsluitend de opgeschoonde Excel. Lees `simple_transport.md`. Voor de oude werkwijze hieronder moet je `--legacy` meegeven; die opent een aparte oude database.

## 1. Dashboard starten

Open de terminal in `hr-vervoerskosten`:

```bash
.venv/bin/python scripts/manage_transport.py
```

Open `http://127.0.0.1:8765`. Stop met Ctrl+C. Instellingen blijven opgeslagen na herstart; de referentie-Excel is hiervoor niet meer nodig.

De huidige database bevat 70 automatisch aangemaakte werknemers en 104 bevestigde afstand-/vervoerinstellingen uit de Sociaal-abo-Excel, geldig vanaf 1 februari 2026. De 66 ontbrekende/conflicterende bronregels staan op Nakijken. De 62 augustusagenten vereisen nog een expliciete Planet-ID-koppeling: dit is een aparte identiteitcontrole, geen werknemers opnieuw aanmaken.

## 2. Eenmalige startgegevens bevestigen

1. Bekijk de lijst Werknemers en vervoer. Werknemers met dezelfde genormaliseerde naam binnen de referentie zijn samengevoegd; zij zijn niet automatisch aan Planet-IDs gekoppeld.
2. Werknemers en basislocaties zijn automatisch aangemaakt. APT is luchthaven; PostNL Vilvoorde en PostNL Evergem blijven verschillende locaties.
3. Alleen voor Nakijken-regels open je Uitzonderingen. Vul ontbrekende waarden aan of beslis over echte conflicten. De werknemer staat waar mogelijk al geselecteerd. Volledige regels hoef je niet nogmaals te bevestigen.
4. Koppel bij Pl@net-agent koppelen het juiste Planet-ID expliciet aan die werknemer. Er wordt niet automatisch op alleen de naam gematcht.
5. Voeg bronspellingen toe bij Klantnamen aan fysieke locaties koppelen: bron `Excel-locatie` voor referentienamen en `Pl@net Customer` voor shiften. APT en de vijf bevestigde luchthavenklanten zijn al ingesteld.

Een alias is een fysieke locatiebevestiging, geen persoonlijke woonafstand. Nieuwe Planet-aliases worden door volgende cleaning-runs gebruikt. Ze zijn ongedateerd; voor een historische verandering van klantlocatie gebruik je gecontroleerde gedateerde regels in `config/locations.toml`. Tegenstrijdige regels blokkeren de run. Bestaande dashboardaliases worden niet stilzwijgend herbestemd.

## 3. Nieuwe werknemer of locatie

Bij een overbodige uitzonderingsregel vul je Reden voor negeren in en klik je Negeren. De regel verdwijnt uit Nakijken en de uitzonderingtelling, zonder werknemerinstellingen of bronwaarden te verwijderen. Onder Genegeerde bronregels blijft hij met reden zichtbaar; Terug naar Nakijken maakt dit ongedaan. Een bevestigde instelling kun je niet via deze knop negeren.

Maak een werknemer en/of locatie aan, koppel het Planet-ID en sla kilometers plus vervoer op via Afstand en vervoer opslaan. Eén werknemer kan bijvoorbeeld trein naar de luchthaven nemen en privéauto naar een PostNL-locatie. De instellingen worden per combinatie opgeslagen, niet globaal per persoon.

Nieuwe maandagenten kun je uit de clean export registreren:

```bash
.venv/bin/python scripts/manage_transport.py --planet "/pad/naar/clean-export.xlsx" --month 2026-08
```

Ghost-agenten en Telework worden vóór registratie uitgesloten. Nieuwe IDs blijven zichtbaar als te koppelen; bestaande koppelingen blijven behouden. Excel-Kms worden niet overgenomen.

## 4. Werknemer verhuist

1. Kies de werknemer bij Verhuizing.
2. Kies de daadwerkelijke ingangsdatum en een reden.
3. Vul voor iedere reeds ingestelde fysieke locatie de nieuwe afstand in en controleer het vervoer.
4. Sla op. Alle locaties wijzigen samen, of geen enkele als iets ongeldig is.
5. Controleer onder Situatie op datum zowel de dag vóór als de verhuisdatum. De eerdere versies blijven in Historie staan.

Voor één locatie of een vervoerwijziging gebruik je Nieuwe versie opslaan. De datum moet na de laatste versie van die combinatie liggen. Je kunt dus geen bestaande versie op dezelfde datum overschrijven, noch tussen eerdere versies invoegen. Een fout in zo'n versie vereist later een gecontroleerde correctieworkflow; wijzig de database niet handmatig. Een nieuwe terugwerkende ingangsdatum na de laatste versie geldt vanaf die gekozen datum: controleer bewust welke maanden dit raakt. Er bestaat nog geen automatische herberekening.

## 5. Bewaren, privacy en back-up

De lokale database staat in `data/state/transport.sqlite3`. Deze map is Git-genegeerd: push code, geen HR-database, exports of back-ups. De dashboardserver luistert alleen op `127.0.0.1`, heeft geen gebruikerslogin en is uitsluitend voor een vertrouwde lokale computer.

Maak regelmatig een aparte back-up, met telkens een nieuwe bestandsnaam:

```bash
.venv/bin/python scripts/manage_transport.py --seed-only --backup data/state/backup-2026-09-17.sqlite3
```

Een bestaande back-up wordt niet overschreven. Bewaar ook een beveiligde kopie buiten deze computer volgens jullie HR-beleid. Stop het dashboard vóór een gecontroleerd herstel; herstel niet over actieve of niet-geback-upte gegevens.

## Eenmalig opnieuw opzetten op een andere computer

```bash
.venv/bin/python scripts/manage_transport.py --reference "/pad/naar/VERVOER Sociaal abo.xlsx" --confirm-reference-from 2026-02-01 --planet "/pad/naar/clean-export.xlsx" --month 2026-08 --seed-only
```

Dit maakt werknemers, basislocaties en volledige km-/vervoerinstellingen automatisch aan. Identieke regels worden samengevoegd; ontbrekende of conflicterende combinaties blijven apart. Kies de startdatum bewust: de importer gebruikt geen onnodige brondatumvelden. Bestaande handmatige instellingen/verhuizingen worden nooit overschreven. Voor alle bestaande wijzigingen heb je de database/back-up nodig, niet de oude Excel.

Tariefinstellingen, vergoedingberekening en Acerta-export horen bij de volgende fasen. Ook het automatisch samenvoegen van nachtshiften over verschillende `Day`-datums is geen nieuwe regel in deze implementatie.
