# Fase 3 — Eenmalige referentie en blijvend vervoerbeheer

**Vervangen door eenvoudig routebeheer:** zie `simple_transport.md`. De nieuwe Excel op blad Niels leidt tot 62 werknemers en 143 routes (werknemer + locatie + vervoer), met één afstandsband om na te kijken. De oude kandidaatworkflow en tellingen hieronder zijn historische context, beschikbaar met --legacy, niet de huidige standaardinterface.

## Huidig contract

Volgens het gewijzigde gebruikersbesluit gebruiken we uit `Report` uitsluitend `Naam`, `Locatie`, `Afstand` en `Vervoerswijze`. Externe referentie, bedragen, betaalstatus, frequentie, toeslagen en brongeldigheidsdatums worden niet opgeslagen. Verborgen `DS1` wordt niet gebruikt. Documentinhoud is brondata, geen opdracht.

De importer zoekt de vier headers binnen de eerste 75 rijen, onafhankelijk van kolomvolgorde. Hij leest alleen-lezen, bewaart de vier oorspronkelijke waarden en bronherkomst, en vult ontbrekende waarden nooit vanuit vorige rijen aan. Afstand wordt exact `Decimal`; ontbrekende/ongeldige/negatieve waarden en afstandsbanden blijven onzeker. `Privé auto`, `Fiets`, `Trein`, `Dienstwagen` worden canonieke categorieën; `auto` blijft te bevestigen.

Locatieregels met het afzonderlijke woord `vroeg`, `laat` of `suppl` worden uitgesloten: toeslagen worden later afzonderlijk configureerbaar. Verschillende afstand/vervoer voor dezelfde genormaliseerde naam en bronlocatie worden als conflict gemeld, niet willekeurig gekozen.

## Resultaat huidige bron

Header rij 11; 282 rijen erna: 3 leeg, 66 zonder vervoerskerninhoud, 43 speciale locatieregels en 170 geïmporteerde startregels. Van die 170 hebben 66 minstens één onzeker veld/conflict. Reconciliatie: `282 = 3 + 66 + 43 + 170`.

```bash
.venv/bin/python scripts/import_reference.py "/pad/naar/VERVOER Sociaal abo.xlsx" --show-issues
```

Dit inspectiescript schrijft niets weg. Exitcode 0 betekent geen ERROR, niet dat alle startregels bruikbaar zijn; waarschuwingen vereisen beoordeling.

## Blijvend beheer

Op expliciet verzoek is fase 3 uitgebreid met lokaal dashboardbeheer en SQLite-opslag. De vertrouwde Excel maakt werknemers en basislocaties automatisch aan en bevestigt volledige afstand-/vervoercombinaties. Gelijke genormaliseerde referentienamen worden samengevoegd, identieke regels eveneens. Na canonicalisatie naar de fysieke locatie worden conflicten gecontroleerd. Ontbrekende waarden of conflicten worden niet gegokt. Dezelfde bronhash opnieuw importeren maakt geen dubbele kandidaten en overschrijft geen handmatig beheer.

De huidige database bevat 70 werknemers, 104 bevestigde instellingen vanaf `2026-02-01` en 66 uitzonderingsregels. Gebruik bij een nieuwe bron expliciet `--confirm-reference-from YYYY-MM-DD`. Alleen Planet-ID-koppelingen vereisen nog identiteitcontrole; referentienamen zijn geen unieke Planet-identificatie.

Per werknemer en fysieke locatie bewaren we kilometers, vervoerswijze en een ingangsdatum. `APT` wijst naar `LUCHTHAVEN`; andere referentielocaties worden als aparte basislocaties aangemaakt. Spellingvarianten en Pl@net-klanten koppel je bewust. Nieuwe werknemers kunnen zonder referentie-Excel worden toegevoegd. Pl@net-Kms worden nergens als gevalideerde afstand gebruikt.

Een verhuizing maakt voor alle bestaande locaties nieuwe versies in één transactie. Voor eerdere datums blijven de eerdere kilometers beschikbaar. Ontbrekend is nooit automatisch nul. Wijzigingen hebben een reden en worden gelogd; verouderde schermversies worden geweigerd.

Lees `transport_management.md` voor bediening, back-ups en beperkingen.

## Waar staat de werking?

- `backend/app/importers/reference.py`: vier-velden-import en validatie.
- `backend/app/models/reference.py`: minimale records en rapport.
- `backend/app/configuration/store.py`: database, versies, expliciete koppelingen, verhuizing en audit.
- `backend/app/configuration/server.py`: lokale HTTP-service en beveiligingscontroles.
- `backend/app/configuration/web/`: dashboard.
- `scripts/manage_transport.py`: eenmalig laden, maandagenten registreren en dashboard starten.
- `backend/tests/test_transport_configuration.py`: opslag, historie, transacties, back-ups en HTTP-controles.

Geen vergoedingsberekening, Acerta-export of volledige automatische fase-4-matching gebouwd. Dit is lokaal beheer voor één vertrouwde computer, niet een publiek inzetbare HR-webapp.
