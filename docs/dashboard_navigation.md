# Dashboardindeling

De interface heeft vijf gescheiden onderdelen:

- Werknemersroutes: de bestaande vervoerswijzen en afstanden, naamcorrecties
  en het oudere route-verhuisformulier.
- Woonadressen: opgeslagen agentadressen en hun coördinaten. Het adresformulier
  en de Mapbox-aanvraagopties staan onder uitklapbare blokken.
- Werklocaties: fysieke locaties, gekoppelde klanten, adressen en coördinaten.
  Adres aanpassen/toevoegen opent het formulier; Mapbox-opties zijn uitklapbaar.
- Maandshiften: exportupload, maandkeuze, shiften en controleberekeningen.
- Instellingen: gedateerde autotariefversies.

Woonadressen en werklocaties hebben elk peildatum- en historiekbediening. Die
gebruiken dezelfde onderliggende datum/historiekkeuze als werknemersroutes.
De actieve tab blijft bij opslaan/vernieuwen behouden en wordt voor deze
browser-tab onthouden zonder HR-data in browseropslag.

Dit is uitsluitend een weergavewijziging. De SQLite-database, klantkoppelingen,
adresversies, coördinaten, shiften en calculaties worden niet aangepast.
Een lokale SQLite-backup is gemaakt vóór deze UI-wijziging. De tabellen zijn
nadien vergeleken met die backup; alle gegevens zijn behouden.
