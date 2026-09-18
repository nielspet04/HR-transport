# Fase 5 — gewone auto en maandelijkse upload

## Starten en testen

1. Herstart de lokale server: `.venv/bin/python scripts/manage_transport.py`.
2. Herlaad `http://127.0.0.1:8765`.
3. Kies bij **Nieuwe Pl@net-export verwerken** de rechtstreekse `.xlsx`-export.
4. Klik **Uploaden en automatisch verwerken**. Alle maanden worden geïmporteerd,
   opgeschoond en gekoppeld. Gewone autoritten worden automatisch berekend.
5. Kies de maand en agent in **Maandshiften · fase 4 + 5**. De nieuwste maand uit
   een upload wordt geselecteerd. Filter op **Nakijken** en **Nog niet in deze fase**.

Een upload is maximaal 5 MB. Het bronbestand wordt nooit overschreven; een private
kopie wordt bewaard naast de database in `planet_uploads/`. Bij een fout worden
geen gedeeltelijke maandresultaten opgeslagen en wordt alleen de mislukte kopie
verwijderd. De kopie wordt bij latere bevestigingen en vernieuwen opnieuw gebruikt.
Werknemers zonder koppeling blijven zichtbaar; ze krijgen geen bedrag. Bestaande
naam-/locatiekoppelingen en afstandsversies blijven intact.

## Berekening

De pure engine staat in `backend/app/calculation.py`. Eén fase-2-beweging leidt
tot één controleregel, ook met meerdere bronshiften of een fietsroute als alternatief.
Auto is de standaard conform het bronproject; dit is nog geen bevestiging van
feitelijk fietsgebruik per dag. Alleen één eenduidige route `Auto` of `Privé auto`
wordt gebruikt. Meerdere autoroutes, auto samen met trein of dienstwagen worden
niet stilzwijgend opgelost.

De gebruiker bevestigde de PDF `accg-pc-317-vervoerskosten_9.pdf` als starttabel:
de gewone 120%-kolom vanaf **01/02/2026**. Het bedrag bevat de 120% reeds. De afstand
is **enkele reis**, zonder factor 2. Voorbeeld: 17 km geeft €7,11 per beweging.
Boven 60 km: tabelbedrag voor 60 km plus €0,31 per extra km. Bedragen worden met
Decimal berekend en op twee decimalen afgerond (ROUND_HALF_UP), niet met floats.
Pl@net-Kms worden nooit gebruikt als afstandsgrondslag.

De prestatiedatum kiest de afstandsversie én tariefversie. Januari heeft geen
bevestigd tarief en krijgt geen februari-fallback. Ontbrekende afstanden,
afstanden onder 1 km en afstanden met decimalen blokkeren de berekening. Een
afrondingsbeleid voor niet-gehele km is nog niet bevestigd.

Vroeg/laat en 48h worden **niet** als gewone auto berekend. Gebruikersbesluit:
uitsluitend het **startuur** bepaalt vroeg/laat: vanaf 22:00 (inbegrepen) tot
06:00 (niet inbegrepen). Einduur en volgende einddag spelen hierbij geen rol.
19:00–07:00 en 19:00–05:00 zijn dus normaal; 05:00–19:00 is speciaal.
Een speciale start of exact `48h_ICTS_Extra_Shift` op één onderliggende shift
zet de volledige beweging apart voor fase 6. Dit beslist nog niet welke
speciale toeslag geldt. Andere Remarks blijven buiten deze tariefselectie.

Trein blijft `n.v.t.` en uitgesloten, zonder ontbrekende-km-probleem. Fiets,
dienstwagen en onbekende vervoerswijzen worden nog niet berekend in fase 5.

## Tarieven eenvoudig wijzigen

Open **Instellingen · tarieven**. De tabel toont alle afstandsbanden met een
bedraginput en het extra bedrag per km boven 60 km. Vul de nieuwe bedragen,
ingangsdatum en reden in, en klik **Tariefversie opslaan**. Er wordt een volledige
nieuwe versie opgeslagen, geen losse ongedateerde wijziging.

Een nieuwe datum moet op of na de laatste ingangsdatum liggen. Een correctie op
dezelfde datum bewaart de vorige versie; de nieuwste versie met die datum geldt
bij herberekenen. Oude versies zijn selecteerbaar ter controle. Na opslaan staat
een oud maandoverzicht op gewijzigd; klik **Vernieuwen** om de volledige bron
bewust opnieuw te verwerken. Een volgende upload gebruikt automatisch de juiste
opgeslagen versie. Oude maandresultaten behouden hun oude controlebedragen.

## Controle en grenzen

Elke controleregel bewaart status, reden, afstand, route-ID/ingangsdatum,
tarief-ID/ingangsdatum, bron en gebruikte tabelregel inclusief eventueel extra km.
De tellingen onderscheiden berekend, nakijken, latere fase en trein.

**Geen definitief uitbetalingsbestand:** maandaggregatie, weekmaximum (7/5),
onderbroken diensten, havenzone-/oproep-/pooluitzonderingen en speciale toeslagen
zijn nog niet verwerkt. Ook de actuale vervoerskeuze per dag komt later.
`payroll_ready` is daarom altijd `false`. Er is geen Acerta-export in deze fase.
Geen bedrag is een expliciete blokkering/uitsluiting, nooit een stilzwijgende €0.

## Opslag en back-ups

Tarieven staan in `car_tariffs` in dezelfde lokale database als routes/koppelingen.
Berekeningen staan in de bewaarde maandmomentopnamen. Uploadkopieën staan naast
de database; Git negeert deze HR-bestanden. Automatische OneDrive-back-ups zijn
nog niet ingesteld: het bestemmingspad is nog niet opgegeven. Voor volledig
herstel zijn de database én de uploadmap nodig, plus `config/locations.toml`.

## Tests

`backend/tests/test_calculation.py` test onder meer tabelgrenzen, lange afstanden,
historische tariefkeuze, correcties, onzekere afstanden, speciale bronshiften,
transportconflicten, nieuwe agenten, upload/HTTP, herstel na fouten en het bewaren
van bronkopieën en oude berekeningsmomentopnamen. Fictieve gegevens; geen HR-data
in Git. Volgende fase: speciale autologica, pas na bevestiging van de voorwaarden.
