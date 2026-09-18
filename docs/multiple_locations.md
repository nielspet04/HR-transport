# Meerdere werklocaties op één dag

Fase-2-bewegingen worden per werknemer en startdatum geordend op bronshifttijden.
Eerste beweging: thuis → locatie. Volgende beweging: vorige → huidige locatie.
Voor drie locaties ontstaat A→B→C, nooit opnieuw thuis→B of thuis→C.
Alle bronshiften van een gegroepeerde beweging bepalen het tijdinterval; overlap,
gelijke/onduidelijke start, ontbrekende tijden of een onzekere koppeling blokkeren
de dag. Eindtijden over middernacht krijgen hun dag-offset. Een verplaatsing over
verschillende startdatums wordt niet zonder extra bevestiging aan elkaar gekoppeld.

De extra beweging gebruikt **altijd de standaard-autotabel** op prestatiedatum,
met de afgeronde enkele tussenlocatie-km. Geen €0,4326, geen maal twee, geen
vroeg/laat- of 48h-vergoeding op die extra beweging. De eerste beweging behoudt
haar gewone standaard/vroeg-laat/48h-regel. Dit is het bevestigde gebruikersbesluit.

Werknemersroutes bereidt de benodigde gerichte locatieparen voor. Auto als
standaard wanneer ingesteld; een fiets-only extra beweging vraagt cycling voor
de afstand, maar fietsvergoeding/kalenderkeuze blijft een volgende stap.
Elke concrete coördinatenpaar/profiel-combinatie wordt één keer aangevraagd,
met PENDING-intentie vóór de aanvraag, blijvende afstand/routelijn en auditcontext.
Een gewijzigd locatieadres vormt een nieuwe context. HR-correcties blijven
werknemer-specifiek. Oude woon-werkafstanden worden niet verwijderd of aangepast.

Maandshiften heeft aparte groepen en een filter **Meerdere werklocaties**.
Zolang de benodigde tussenafstand ontbreekt staat de extra beweging zonder bedrag.
Mapbox wordt nooit door de controleberekening zelf aangeroepen. Vraag de nieuwe
routes bewust op onder Werknemersroutes; nieuwe Excelcontroles gebruiken daarna
de tussenlocatieafstand. Geen impliciete extra rit naar thuis, geen payroll-export.
