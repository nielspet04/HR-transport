# 48h-extra-shift: heen en terug

Bij de exact bevestigde Planet-remark 48h_ICTS_Extra_Shift kiest de beweging
de aparte 48h-regel, ook als de shift 's nachts begint.
Afgeronde enkele auto-km × 2 × het kilometertarief geldig op prestatiedatum.
Voorbeeld: 17,001 km wordt 18 enkele km → 36 km × €0,4326 = €15,57.
Geen standaard/vroeg-laat-tabelbedrag erbij; geen +60km-toeslag.
Alleen het eindbedrag wordt op centen afgerond (ROUND_HALF_UP).
Een HR-afstandscorrectie heeft voorrang op Mapbox. Geen nieuwe API-aanvragen.

Instellingen → Tariefsoort → 48h-extra-shift toont het instelbare km-tarief,
ingangsdatum en verplichte wijzigingsreden. Vier decimalen maximaal; komma mag.
Starttarief €0,4326 vanaf 01/02/2026 sluit aan op de aangeleverde PDF-startperiode.
Eerdere datums krijgen geen geraden historisch tarief. Nieuwe versies blijven
bewaard in extra_shift_tariffs in dezelfde private SQLite-database.
Een correctie op de laatste ingangsdatum maakt een nieuwe logregel; oudere regels
blijven opgeslagen. Instellingen werken bij herladen door in de controleberekening.

Fase-2-deduplicatie blijft gelden: één roundtrip per behouden beweging, niet per
onderliggende dubbele bronshift. Dagen met meerdere werklocaties blijven apart
tot de trajectberekening gebouwd is. Ontbrekende autoafstand/tarief/koppeling
blijft geblokkeerd. Weekmaximum en fietskeuze volgen later: geen payroll-export.
