# Configureerbare businessregels

Gebruikersbesluit 2026-09-16: alles wat bedrijfsmatig nog niet 100% vaststaat moet later centraal aanpasbaar zijn vanuit het dashboard. Voorbeeld: fietsvergoeding per kilometer.

Deze pagina legt de ontwerpafspraak vast. Er zijn in fase 1 geen tarieven, settings-services, API-endpoints of dashboard gebouwd.

Update fase 3: op expliciet verzoek is lokaal dashboardbeheer gebouwd voor werknemer, fysieke locatie, alias, vervoer en afstand. SQLite bewaart gedateerde versies; een verhuizing wijzigt alle reeds ingestelde locaties atomair. De referentie-Excel is alleen eenmalige startbron. Tarieven en berekeningen zijn nog niet gebouwd. Zie `transport_management.md`. Het ontbreken van een dashboard in onderstaande fase-1/2-beschrijvingen is historische fasecontext.

## Afspraak

- Geen onzeker tarief of beleidskeuze verspreid hardcoden in berekeningsfuncties.
- Eén gevalideerde instelling per regel; de calculation engine ontvangt deze instellingen expliciet.
- Een ontbrekende noodzakelijke waarde betekent unresolved, niet automatisch nul of een fictief standaardtarief.
- Bewaar waar nodig een ingangsdatum/periode: een wijziging voor vandaag mag een historische maand niet stilzwijgend veranderen.
- Bewaar bij een latere berekening de gebruikte instellingenversie en waarde. De review moet kunnen tonen waarom iets zo berekend werd.
- Een latere dashboardwijziging moet bewust herberekenen en traceerbaar zijn.
- Een instelling vervangt geen onzekere werknemer-/locatiematch. Onzekere mappings blijven `UNMATCHED` of `AMBIGUOUS` totdat HR een expliciete mapping bevestigt.
- Bronformaatvalidatie is geen vrije businessparameter. Een ongeldige datum wordt niet geldig door een dashboardtarief te wijzigen.

## Nog vast te leggen instellingen

| Regel | Onzekerheid | Fase waarin implementatie hoort |
| --- | --- | --- |
| Fietstarief per km | Projectbrief: €0,37; aangeleverde PDF: €0,36. Waarde en geldigheidsdatum nog niet definitief. | 8 |
| Atypische uren | Bevestigd: uitsluitend startuur, vanaf 22:00 inbegrepen tot 06:00 niet inbegrepen. Einduur bepaalt geen toeslag. Speciale tariefselectie volgt in fase 6. | 6 |
| Speciale/48u-tariefselectie | Expliciete locatie-/tariefmapping nog te bevestigen; geen multiplier verzinnen. | 6 |
| Afwezigheids-/cleaningcategorieën | Eerst de 28 echte Remark-waarden van de actieve bron onderzoeken. Onbekende codes niet blind verwijderen. | 2 |
| Nachtshiftinterpretatie | Bij eindkloktijd vóór startkloktijd ontbreekt expliciete einddatum; eventueel rolloverbeleid moet zichtbaar worden gekozen. | Pas wanneer einddatum/dienstduur nodig is |
| Trein- en bedrijfswagenstatus | Beheerbare werknemerstatus/overrides; brongegevens en HR-besluit moeten traceerbaar blijven. | 7 |

De maandkeuze is in fase 1 al een expliciete importerparameter. De tijdnotatie `24:00` is geen onzekere toeslagregel: deze bevat zelf de volgende middernacht en wordt als brongegeven bewaard.

## Fase 2: cleaningpolicy

Nieuw besluit: Pl@net-Kms zijn onbetrouwbaar. De kilometergebaseerde suggestielogica is verwijderd; locaties worden uitsluitend handmatig bevestigd. ICTS BELGIUM BVBA is als vijfde luchthavenklant bevestigd. De CLI laadt gedateerde regels/versie uit `config/locations.toml`; overlap/conflicten blokkeren de run. Later mogen bron-Kms niet als gevalideerde berekeningsafstand gebruikt worden. Zie `location_review.md` voor handmatig beheer en historische perioden.

Gebruikersbevestiging luchthaven: Customers `DELTA AIRLINES`, `HAINAN AIRLINES`, `LATAM CARGO`, `TUI` horen bij één fysieke locatie. De centrale `CleaningPolicy.location_aliases` bevat deze vier expliciete namen gekoppeld aan `LUCHTHAVEN`. Geen substring-/fuzzy airlineherkenning. Per werknemer/dag één beweging op deze fysieke locatie, ongeacht onderbrekingen in uren. Bron-Customer en alle bronshiften blijven bewaard. Deze groepering bepaalt nog geen vervoersreferentie, afstand of tarief; verschillen daarin mogen later niet via een willekeurige eerste shift worden opgelost.

Gebruikersbevestiging: Id `1112`, `1113`, `1114`, `1115`, `1116` zijn ghost-agenten. `CleaningPolicy.ghost_employee_ids` bevat deze standaardlijst centraal en blijft expliciet overschrijfbaar door een toekomstige settingslaag. Exacte tekst-ID-vergelijking; geen numerieke conversie of substringmatching. Alle geselecteerde shiften van deze IDs worden eerst uitgesloten als `GHOST_AGENT`, ongeacht locatie, uren of Remark. Zo telt een ghost-Telework-shift slechts één keer als ghost. Uitgesloten bronshiften blijven traceerbaar in `removals`, niet in de behouden bewegingen. De importer blijft de volledige bron valideren, ook voor ghost-rijen; deze businessregel omzeilt geen bronvalidatie.

`CleaningPolicy.excluded_remarks` bevat uitsluitend expliciet bevestigde extra uitsluitingscodes en wordt aan de pure cleaningfunctie meegegeven. Standaard leeg: geen verzonnen afwezigheidsmapping. Telework is de expliciete regel uit de projectbrief. Andere niet-lege Remarks blijven unresolved behouden; ook bij deduplicatie blijft hun bronshift bewaard. De CLI vereist een expliciete maand of `--all-months`. Geen settings-API of dashboard in deze fase; zie `phase_2.md`.
