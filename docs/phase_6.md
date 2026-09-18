# Vroeg/laat auto: aparte kilometertabel

Vanaf deze implementatie gebruikt de actuele controleberekening de speciale
150%-kolom van accg-pc-317-vervoerskosten_9.pdf, geldig vanaf 01/02/2026.
Het exacte tabelbedrag vervangt de standaardtabel; geen multiplier of extra toeslag.
Voor 18 km: €9,22. Voor 60 km: €19,96; boven 60 km +€0,31 per extra km.

Uitsluitend de START telt: 22:00 inbegrepen tot 06:00 niet inbegrepen.
19:00–07:00 en 19:00–05:00 zijn standaard; 05:00–19:00 is speciaal.
Bij fase-2-groepering krijgt een beweging met een bijzondere start op één
onderliggende bronshift één speciaal tabelbedrag, geen dubbele betaling.
48h-oproepen zijn expliciet apart opgeslagen en blijven voor een volgende regel.
Ook meerdere werklocaties per dag, bedrijfswagen en weekmaximum blijven buiten
deze eenvoudige berekening. Trein is uitgesloten; fietskeuze volgt later.

Mapbox/HR-afstanden zijn enkele kilometers, altijd naar boven afgerond.
Ontbrekende speciale tariefversie blokkeert: geen standaardtarief als fallback.
Instellingen → Tariefsoort → Vroeg/laat toont de volledige aanpasbare tabel.
Nieuwe versies hebben een ingangsdatum en reden, oud blijft bewaard.
Speciale tariefversies worden bij herladen op prestatiedatum gekozen.

De policyversie vereist nieuwe shiftverwerkingen zodat vroeg/laat en 48h veilig
gescheiden worden. Het huidige bronbestand is na een databaseback-up vernieuwd.
Historische verwerkingen blijven opgeslagen en verouderde snapshots blokkeren.
Er zijn geen nieuwe Mapbox-aanvragen gedaan. Nog geen uitbetalingsbestand.
