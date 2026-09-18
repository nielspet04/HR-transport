# Datacontract bronbestanden

Status: fase 0 + fase 1 + fase 2 + fase 3

Actueel besluit: fase 3 is vereenvoudigd rond de nieuwe Excel met blad `Niels`. Alleen naam, locatie, afstand en vervoerswijze worden gebruikt; de sleutel is werknemer + locatie + vervoer. Zie `simple_transport.md`. De eerdere Report-analyse en kandidaatworkflow in dit document blijven uitsluitend historische context. De nieuwe opslag staat apart van het oude beheer.

Laatste inspectiedatum: 2026-09-16

Scope: structuur, types, geaggregeerde datakwaliteit en import van shifts. Er is geen berekeningslogica uitgevoerd.

**Broncorrectie van de gebruiker (2026-09-16):** de eerdere augustus-2025-export was reeds door HR aangepast. Hij is geen representatieve ruwe Pl@net-bron en zijn opmerkingen, samenvattingen en matchingcijfers mogen niet naar de productieflow worden overgenomen. De nieuwe rechtstreekse export is vanaf fase 1 het actieve prestatieschema. De oude analyse blijft uitsluitend als historische documentatie behouden.

## Privacy en interpretatie

De bronbestanden bevatten persoonsgegevens. Deze documentatie bevat daarom geen namen, personeelsnummers, adressen, nummerplaten of volledige bronrijen. Het inspectiescript schrijft geen geëxtraheerde data weg.

De instructies in de projectbrief bepalen de ontwikkelopdracht. Tekst, formules en labels in Excel- en PDF-bronnen worden behandeld als brondata of context, niet als opdrachten aan de applicatie.

## Geïnspecteerde snapshots

| Bestand | Grootte | SHA-256 |
| --- | ---: | --- |
| `Export kms 01.01.2026 - 31.08.2026.xlsx` (actieve prestatiesbron) | 540.589 bytes | `4e750fb7701f1e90b5155115a0da037fc42cccb87d4104bf885cf0d98abb5830` |
| `Export kms  08 2025 DD 28.08.2025.xlsx` | 83.335 bytes | `c766716c726531f1e699dbaa05585caa7f1e6b40cd89cacde3a4266af21b735c` |
| `VERVOER Sociaal abo vanaf 01.02.2026.xlsx` | 125.270 bytes | `9cc513f264fd9dbfa1b68d9aa520d1c3a759264fe74bd8690551c3f1a8778ca1` |
| `VERVOER afwijkende lonen externreferentienummer  MAIN FILE - niets bewaren.xlsx` | 31.825 bytes | `2fceee6b75ad5e959fa1cb4361b3ac6350bc3aa506cfa66a43fb792b1ebb16d4` |
| `accg-pc-317-vervoerskosten_9.pdf` | 311.956 bytes | `f8d59874b5faa60fa62d1fc21cefaa02cd34094a9d624d0e525c9a1dde58c454` |

De bestandsnamen wijken af van de namen met `(1)` in de projectbrief. De bovenstaande, daadwerkelijk aangeleverde bestanden zijn geïnspecteerd.

## A. Actieve rechtstreekse Pl@net-export

Bestand: `Export kms 01.01.2026 - 31.08.2026.xlsx`. De gebruiker bevestigt dat deze structuur rechtstreeks uit Pl@net komt. Deze testexport bundelt meerdere maanden; normaal is de import één maand per bestand.

- Eén zichtbaar werkblad: `Total kms`.
- Header rij 1; precies 11 kolommen A:K, in deze volgorde:

```text
Id | Last name | First name | Department | Day | Task
Debut tache | Fin tache | Remark | Customer | Kms
```

- 9.473 werkbladrijen: één header en 9.472 datarijen.
- Geen lege datarijen, `Total`-regels of herhaalde headers aangetroffen.
- Alle ID's zijn tekst; voorloopnullen worden behouden. 70 verschillende ID's.
- `Last name`, `First name`, `Day`, `Task`, `Debut tache`, `Fin tache`, `Customer` en `Kms` zijn op alle datarijen gevuld.
- `Department` ontbreekt op 738 rijen en is daarom een optioneel bronveld.
- `Remark` is leeg op 7.565 rijen. Er zijn 1.907 niet-lege opmerkingen met 28 verschillende waarden. Ze worden zonder whitelist of businessinterpretatie geïmporteerd. Het onderzoeken van cleaningcategorieën hoort bij fase 2.
- `Day` is tekst in formaat `YYYY-MM-DD`, van 2026-01-01 t/m 2026-08-31.
- Start/eindtijd zijn tekst in formaat `HH:MM`. Vier eindtijden zijn expliciet `24:00`. Die worden als `00:00` met bron-dagoffset +1 vastgelegd.
- Op 715 andere rijen ligt de eindkloktijd vóór de startkloktijd. Deze worden behouden met `END_BEFORE_START`. Er wordt niet automatisch een volgende einddatum gekozen.
- `Kms` bevat 9.472 numerieke waarden, geen formules. Dit is een bronwaarde, niet automatisch de vergoedbare afstand of een tariefgrondslag.

| Bronmaand | Geïmporteerde shifts |
| --- | ---: |
| 2026-01 | 867 |
| 2026-02 | 747 |
| 2026-03 | 1.008 |
| 2026-04 | 1.219 |
| 2026-05 | 1.265 |
| 2026-06 | 1.475 |
| 2026-07 | 1.485 |
| 2026-08 | 1.406 |
| Totaal | 9.472 |

De fase-1-importer accepteert deze structuur en vereist geen HR-verrijkingen. Zonder maandparameter worden alle geldige shifts behouden, met `MULTIPLE_MONTHS` indien toepasselijk. Met een expliciete `YYYY-MM`-parameter worden geldige rijen buiten die maand apart geteld. Validatiefouten in de rest van het bestand blijven zichtbaar. Een niet-aanwezige gekozen maand levert `MONTH_NOT_PRESENT` op, niet een stilzwijgend succesvol leeg resultaat.

Zie `docs/phase_1.md` voor veldtypes, foutcodes, telreconciliatie en testinstructies.

## A-historisch. Door HR aangepaste maandelijkse prestaties

Bestand: `Export kms  08 2025 DD 28.08.2025.xlsx`

### Werkmapstructuur

- Eén zichtbaar werkblad: `Total kms`.
- Gebruikt bereik volgens openpyxl: 1.365 rijen en 15 kolommen.
- De echte header staat op rij 1.
- Het autofilter is ingesteld op `A1:K1364`, terwijl rij 1.365 ook inhoud bevat. Een importer mag dus niet alleen op het autofilterbereik vertrouwen.
- Kolommen L tot en met O hebben geen header en bevatten geen relevante waarden in de inspectie.

### Werkelijke kolommen A:K

| Kolom | Brontype in datarijen | Lege waarden | Fase-0-observatie |
| --- | --- | ---: | --- |
| `Id` | tekst | 0 | Bevat ook 56 kandidaat-samenvattingsregels met `Total`. |
| `Last name` | tekst | 56 | Leeg op de kandidaat-samenvattingsregels. |
| `First name` | tekst | 56 | Leeg op de kandidaat-samenvattingsregels. |
| `Department` | tekst | 56 | Leeg op de kandidaat-samenvattingsregels. |
| `Day` | tekst | 56 | Alle 1.308 niet-lege waarden volgen `YYYY-MM-DD`; dit zijn geen native Excel-datums. Bereik: 2025-08-01 t/m 2025-08-31. |
| `Task` | tekst | 56 | Vrije operationele taaknaam; niet als locatie of tariefregel interpreteren zonder expliciete mapping. |
| `Debut tache` | tekst | 56 | Alle 1.308 niet-lege waarden volgen `HH:MM`; dit zijn geen native Excel-tijden. |
| `Fin tache` | tekst | 56 | Alle 1.308 niet-lege waarden volgen `HH:MM`; dit zijn geen native Excel-tijden. |
| `Remark` | tekst | 1.004 | 360 niet-lege waarden, verdeeld over 12 aangetroffen categorieën. |
| `Customer` | tekst | 56 | Kandidaat-locatieveld. In deze snapshot zijn geen loutere casing-/randspatievarianten gevonden. |
| `Kms` | getal of formule | 0 | 1.308 numerieke waarden en 56 formules, waarbij de formules samenvallen met de samenvattingsstructuur. |

### Geaggregeerde bevindingen

- 1.364 niet-lege rijen onder de header.
- 1.308 shiftachtige rijen en 56 kandidaat-samenvattingsregels.
- 55 unieke niet-`Total` ID-waarden.
- 292 groepen voldoen in de ruwe data meermaals aan `[Id + Day + Customer]`; samen zijn dit 353 extra rijen boven één rij per sleutel. Dit is alleen een kandidaatmeting. Verwijderen hoort pas bij fase 2.
- 34 shifts hebben een eindtijd die lexicaal/chronologisch vóór de starttijd ligt. Waarschijnlijk gaat het minstens deels om diensten over middernacht; fase 1 moet dit zichtbaar en testbaar parsen in plaats van een negatieve duur te accepteren.
- Aangetroffen niet-lege `Remark`-waarden en aantallen:

| Remark | Aantal |
| --- | ---: |
| `ICTS_OV` | 159 |
| `ICTS_OV_EXTRA_SHIFT` | 47 |
| `OV_AC` | 41 |
| `48h_ICTS_Extra_Shift` | 31 |
| `OV_DL` | 30 |
| `Administration` | 16 |
| `Telework` | 14 |
| `Agent_OV` | 12 |
| `Wissel` | 5 |
| `TRA_NO_SOC_ABO` | 3 |
| `Verplaatsing` | 1 |
| `OV_PostNl` | 1 |

Alleen `Telework` is nu expliciet als niet-vergoedbaar opgegeven. De overige waarden zijn geen toestemming om ze in fase 1 of 2 automatisch te verwijderen.

## B. Vervoersreferentie

Fase 3 is aangepast volgens het nieuwe gebruikersbesluit; zie `docs/phase_3.md` voor het huidige importcontract. Alleen naam, locatie, afstand en vervoerswijze worden gebruikt. Header rij 11; 170 startrecords, waarvan 66 met onzekerheid, 66 niet-datarijen, 43 uitgesloten speciale locatieregels en 3 lege rijen. Geen forward-fill. Externe referentie, bedragen, betaalstatus en brongeldigheidsdatums worden niet opgeslagen. Het lokale dashboard bewaart expliciete werknemer-/locatiekoppelingen en gedateerde km-/vervoerversies; nog geen automatische matching of berekening. De onderstaande fase-0-observaties en oude open vragen zijn historische broncontext, geen huidige implementatie-eisen.

Bestand: `VERVOER Sociaal abo vanaf 01.02.2026.xlsx`

### Werkmapstructuur

- Zichtbaar werkblad `Report`: 293 rijen en 57 kolommen.
- Verborgen werkblad `DS1`: 121 rijen en 80 kolommen. Dit lijkt ondersteunende werkmapinhoud en is in fase 0 niet als importbron aangewezen.
- De echte header van `Report` staat op rij 11, niet op rij 1.
- Het autofilter van `Report` is `A11:BE284`, terwijl het gebruikte bereik tot rij 293 loopt. Een importer mag niet blind het filterbereik of `max_row` als recordgrens gebruiken.
- Er zijn 10 samengevoegde bereiken, buiten de kern van de gedetecteerde tabelheader.
- Er is geen native Excel-tabelobject.

### Werkelijke kolommen in `Report`

In volgorde, inclusief één lege headerkolom na `Bedrag/eenheid`:

```text
Acerta-sleutel
Naam maatschappelijke zetel
Juridische entiteit
Sturingsgroepcode
Sturingsgroep
Kostenplaatscode
Kostenplaats
Overeenkomstnummer
Externe referentie
Rijksregisternummer
Naam
Tewerkstellingsbreuk Teller
Tewerkstellingsbreuk Noemer
VTE
Aard
Functie
Datum in dienst
Datum uit dienst
Risicocategorie arbeidsongeval
Volgnummer
Woon-werkvervoer uitbetalen
Locatie
Afstand
Bedrag/eenheid
<lege header>
Frequentie
Vervoerswijze
Voertuig wordt effectief gebruikt
Soort abonnement
Tarief periode
Nummerplaat
Merk
Type wagen
Gebruik
Eigen bijdrage
Eigen bijdrage/maand
CO2
Brandstof
Cataloguswaarde
Fiscale PK
Lichte vracht
Datum eerste inschrijving
Datum aanschaffing
Aantal km
Eigen bijdr. aantal km
Hybride
Valse hybride
CO2 niet-hybride (g/km)
Straat
Nummer
Bus
Postcode
Gemeente
Land
Gegevens geldig van
tot en met
Overeenkomsttype
```

### Kernvelden en kwaliteit

- Er staan 279 niet-lege rijen onder de header, maar 93 daarvan bevatten minstens één formule. Niet iedere niet-lege rij is dus automatisch een vervoersreferentierecord.
- `Locatie` is gevuld op 188 rijen. Daarvan hebben 183 een numerieke `Afstand` en 175 een numeriek `Bedrag/eenheid`.
- Van de 188 rijen met een locatie missen 97 een `Externe referentie` en 13 een `Naam`. Dit kan wijzen op vervolg-/groeperingsrijen, maar fase 3 moet de structuur eerst expliciet reconstrueren en valideren. Blind forward-fill is nog geen goedgekeurde regel.
- `Externe referentie + Locatie` bevat één exact herhaalde sleutel boven de eerste rij.
- Tien `Locatie`-cellen hebben leidende of afsluitende spaties. Over alle locatiewaarden zijn acht genormaliseerde namen met meerdere casing-/spellingvarianten gevonden.
- Er zijn 43 locatierijen met `vroeg`, één met `laat` en drie met `suppl` in de locatietekst.
- Op basis van genormaliseerde naam en een locatiebasis zonder het achtervoegsel `vroeg` zijn 31 combinaties gevonden waarin zowel een basislocatie als een vroege variant aanwezig is, verspreid over 29 naamgroepen. Dit bevestigt dat een speciale referentieregel niet door een vaste multiplier mag worden vervangen.
- `Bedrag/eenheid` bevat naast getallen ook lege waarden, tekst en één formule. Fase 3 moet elk recordtype expliciet classificeren.

### Aangetroffen categoriewaarden

`Woon-werkvervoer uitbetalen`:

- `Wel uitbetalen`: 102
- `Niet uitbetalen (informatief)`: 39
- `Niet uitbetalen`: 12
- `niet`: 2
- `NIET`: 1
- twee onverwachte waarden waarvan de inhoud om privacyredenen niet in dit document staat

`Vervoerswijze`:

- `Privé auto`: 110
- `Fiets`: 13
- `Trein`: 7
- `Dienstwagen`: 5
- `auto`: 2
- `Auto`: 1

De casing en benaming van auto zijn niet uniform. Normalisatie moet later expliciet en testbaar gebeuren.

`Frequentie` bevat onder meer `Werkdagen (enkele afstand)` (126), `Fiets enkel` (10), `Dagelijks fiets (heen en weer)` (3), `suppl` (2), `alternatief adres` (1), `suppl vroeg` (1), `auto` (1), `vroeg` (1) en `per dag` (1).

`Tarief periode` bevat `Weekbedrag/5` (102), `Maximale fietsvergoeding` (13), `Weekbedrag/6` (1) en 62 formules. Die formules mogen niet als tariefcategorie worden geïmporteerd.

## C. Acerta-template en bestaand voorbeeld

Bestand: `VERVOER afwijkende lonen externreferentienummer  MAIN FILE - niets bewaren.xlsx`

Dit bestand is alleen geïnspecteerd. Het origineel is niet gewijzigd.

### Werkblad `Afwijkende loonelementen`

- Header op rij 1; 69 niet-lege voorbeeldrijen eronder.
- Gebruikt bereik: 70 rijen en 16 kolommen.
- Het autofilter staat uitzonderlijk op `A1:XFD70`, dus over alle Excel-kolommen. Een latere exporter mag dit niet gebruiken om de echte veldbreedte te bepalen.
- Cel/kolom A heeft als header `Acerta Connect Standaard Template Afwijkende loonelementen (*) verplicht`, maar is leeg in alle 69 voorbeeldrijen.
- De feitelijke exportvelden staan in B:P:

```text
Update code
Extern referentienummer (type HRM-nummer) (*)
Naam werknemer
Loonperiode (*)
Manipulatiecode
Looncode (*)
Eenheden
Bedrag per eenheid
Percentage
Bedrag
Dagen
Kostenplaats
Reden
Startdatum (fractie)
Einddatum (fractie)
```

- `Loonperiode (*)`, `Startdatum (fractie)` en `Einddatum (fractie)` zijn native Excel-datumwaarden in de voorbeeldrijen.
- `Bedrag per eenheid` is numeriek waar gevuld: 66 gevuld en 3 leeg.
- `Eenheden` is slechts op 6 van 69 voorbeeldrijen gevuld.
- `Manipulatiecode`, `Percentage`, `Bedrag`, `Dagen` en `Kostenplaats` zijn in alle 69 voorbeeldrijen leeg.
- `Reden` is op 67 rijen gevuld, op 2 leeg en heeft één waarde met randspatie.

Deze observaties beschrijven het voorbeeld en leggen nog niet vast welke velden de toekomstige exporter moet vullen. Dat wordt pas in fase 12 bepaald.

### Werkblad `LIST NIET UITBETALEN `

Let op: de werkbladnaam bevat een afsluitende spatie.

- Header op rij 1; 84 niet-lege rijen eronder.
- Werkelijke kolommen:

```text
Externe referentie
Naam
Volgnummer
Woon-werkvervoer uitbetalen
Afstand
Vervoerswijze
Voertuig wordt effectief gebruikt
Soort abonnement
Tarief periode
```

- `Externe referentie`, `Naam`, `Volgnummer`, `Woon-werkvervoer uitbetalen`, `Afstand`, `Vervoerswijze` en `Voertuig wordt effectief gebruikt` zijn op alle 84 rijen gevuld.
- `Soort abonnement` is op één rij gevuld.
- `Tarief periode` is op 73 rijen gevuld.

## D. Aanvullende PDF-context

Bestand: `accg-pc-317-vervoerskosten_9.pdf`

- Twee A4-pagina's, titel `BEWAKING - PC 317` en barema's vanaf 01/02/2026.
- Pagina 1 bevat tabellen voor 120% en 150% per enkele-reisafstand, inclusief een aparte behandeling boven 60 km.
- Pagina 2 noemt onder meer openbaar vervoer, andere vervoersmiddelen, onderbroken diensten, atypische uurroosters, lange afstanden, Havenzone Antwerpen, dringende/speciale oproepen, flexibele pool en fietsvergoeding.
- Deze PDF is aanvullende context. De projectbrief bepaalt dat een beschikbare specifieke Excel-referentieregel leidend is. Er is in fase 0 geen tarief uit de PDF gecodeerd.

## Kruisbronobservaties voor latere matching

Deze cijfers zijn historische fase-0-diagnostiek op de door HR aangepaste export, niet op de actieve rechtstreekse bron. Er is nog geen matcher gebouwd. Fase 4 moet de analyse opnieuw uitvoeren op de actieve bron; de onderstaande coveragecijfers zijn niet herbruikbaar.

- Prestatie-export: 55 unieke niet-`Total` ID's.
- Vervoersreferentie: 63 unieke niet-lege externe referenties.
- Exacte overlap tussen `Id` en `Externe referentie`: 0.
- 55 unieke genormaliseerde namen in de prestatie-export.
- 62 unieke genormaliseerde namen op vervoersreferentierijen met een externe referentie.
- Naamvolgorde `First name + Last name` geeft 0 exacte genormaliseerde overeenkomsten met `Naam`.
- Naamvolgorde `Last name + First name` geeft 43 exacte genormaliseerde overeenkomsten; 42 daarvan zijn één-op-één binnen de beschikbare ID/reference-rijen.
- Eén genormaliseerde referentienaam is gekoppeld aan meer dan één externe referentie.

Conclusie: `Id == Externe referentie` is aantoonbaar onjuist voor deze snapshots. Naamvolgorde helpt, maar is niet volledig en niet altijd uniek. Fase 4 moet `UNMATCHED` en `AMBIGUOUS` expliciet ondersteunen en mag geen fuzzy match automatisch accepteren.

## Openstaande datakwaliteits- en businessvragen

Update 2026-09-16: onzekere tarieven en beleidskeuzes worden later configureerbaar, zonder stilzwijgende defaults. Zie `docs/configurable_rules.md`. De oude augustus-2025-cijfers hieronder zijn historische bevindingen; voor de actieve export gelden de aantallen in sectie A.

1. **Vervolg-/groeperingsrijen in `Report`.** Op veel locatierijen ontbreken externe referentie en soms naam. Fase 3 moet bepalen of en onder welke controlewaarden identiteit uit een vorige rij mag worden overgenomen.
2. **Formule- en subtotaalrijen in `Report`.** Minstens 93 rijen bevatten formules. Er is een expliciete recordclassificatie nodig voordat tarieven worden geïmporteerd.
3. **Vroege tariefselectie.** De referentie bevat aantoonbaar basis- en `vroeg`-varianten, maar er is nog geen gevalideerde mapping van shift naar specifieke referentieregel.
4. **Late en 48u-mapping.** Er is slechts één locatierij met `laat` en geen locatierij met `48` in de naam. De selectie van een regel voor late of `48h_ICTS_Extra_Shift`-prestaties is nog onopgelost.
5. **Drempel atypische uren.** De projectbrief noemt start vóór 06:00 of start na 22:00. De PDF beschrijft begin óf einde na 22:00 en vóór 06:00. Dit verschil moet vóór fase 6 worden beslist.
6. **Fietstarief.** De projectbrief noemt configureerbaar €0,37/km. De PDF vanaf 01/02/2026 noemt €0,36/km met automatische koppeling aan het fiscale plafond. Het tarief blijft configureerbaar, maar de effectieve waarde en ingangsdatum moeten vóór fase 8 worden bevestigd.
7. **Onverwachte uitbetalingsstatussen.** Twee waarden in `Woon-werkvervoer uitbetalen` vallen buiten de herkenbare statuscategorieën. Ze mogen niet stilzwijgend als wel/niet uitbetalen worden behandeld.
8. **Nachtshifts.** 34 prestatieregels eindigen qua kloktijd vóór de starttijd. Fase 1 moet een expliciet rolloverbeleid en tests krijgen.
9. **Autocategorieën.** `Privé auto`, `auto` en `Auto` komen naast elkaar voor. De gewenste canonieke categorie moet in fase 3 worden vastgelegd.
10. **Bronperiodeverschil.** De prestatie-export betreft augustus 2025, terwijl de vervoersreferentie en PDF vanaf februari 2026 gelden. Deze snapshots zijn geschikt voor structuur- en matchinganalyse, maar niet zonder meer voor een historisch juiste tariefvalidatie over augustus 2025.

## Contractgrenzen voor de volgende fases

- Fase 1 mag alleen `Total kms` van de rechtstreekse Pl@net-export importeren en typeren.
- Fase 1 herkent de werkelijke header, verwerkt de 11 kernvelden, classificeert eventueel aanwezige `Total`-regels zichtbaar en parseert tekstuele datums/tijden strikt. Lege staartkolommen zijn geen vereiste van de actieve export.
- Fase 1 mag `Remark` nog niet als cleaningregel gebruiken.
- Fase 3 moet `Report` vanaf de echte header op rij 11 analyseren en recordtypen onderscheiden voordat gegevens worden overgenomen.
- Geen enkele fase mag persoonsgegevens of afgeleide HR-records als testfixture opslaan; tests gebruiken fictieve data.
