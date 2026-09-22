# Externe loonreferentienummers

Externe loonreferentienummers staan in de lokale werknemersdatabase. Het zijn
tekstvelden, zodat een voorloopnul nooit verloren gaat. Een wijziging voegt een
nieuwe versie met ingangsdatum toe; eerdere maanden blijven daardoor naar het
nummer kijken dat op de shiftdatum geldig was.

De eerste import gebruikt alleen `Naam` en `Externe referentie` uit het werkblad
`Report`. Exacte namen en namen die al bij de adresimport door HR werden
gekoppeld, worden overgenomen. Onbekende of ambigue namen blijven als bronregel
ter controle staan. De import maakt geen werknemers aan.

In het dashboard staat het nummer naast naam en woonadres. HR kan daar een nieuw
nummer met ingangsdatum en reden opslaan. De maandtotalen bevatten het nummer
al als voorbereidend veld voor de latere Acerta-export. Een ontbrekend nummer of
een nummerwijziging midden in de maand wordt zichtbaar gemeld, maar verandert
het berekende vervoersbedrag niet.
