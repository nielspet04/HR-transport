# Meerdere werklocaties op één dag

Fase-2-bewegingen worden per werknemer en startdatum geordend op bronshifttijden.
Eerste beweging: thuis → locatie. Een volgende beweging gebruikt alleen
vorige locatie → huidige locatie wanneer de pauze tussen het einde van de
vorige en de start van de volgende shift **maximaal 120 minuten** bedraagt.
Bij 121 minuten of meer wordt opnieuw thuis → huidige locatie gebruikt. De
grens wordt inclusief toegepast: exact twee uur is een rechtstreekse transfer.
Alle bronshiften van een gegroepeerde beweging bepalen het tijdinterval; overlap,
gelijke/onduidelijke start, ontbrekende tijden of een onzekere koppeling blokkeren
de dag. Eindtijden over middernacht krijgen hun dag-offset. Een verplaatsing over
verschillende startdatums wordt niet zonder extra bevestiging aan elkaar gekoppeld.

De extra beweging gebruikt de afgeronde enkele tussenlocatie-km. Normaal geldt
de standaard-autotabel en een vroeg/laat-markering wordt niet toegepast op een
verplaatsing na een eerdere werklocatie. Een **expliciete 48h-markering op de
tweede bronshift blijft echter behouden**: tussenlocatie-km × 2 × het gedateerde
48h-tarief. Dit voorkomt dat de classificatie verdwijnt door de routevolgorde.
Fiets gebruikt eveneens de tussenlocatieafstand × 2 × het fietstarief, zonder
vroeg/laat- of 48h-toeslag. Dit vervangt de oudere afspraak dat iedere extra
beweging ongeacht haar expliciete bronmarkering standaardtarief kreeg.

Werknemersroutes bereidt de benodigde gerichte locatieparen voor. Auto als
standaard wanneer ingesteld; een fietsbeweging vraagt cycling voor de afstand.
Elke concrete coördinatenpaar/profiel-combinatie wordt één keer aangevraagd,
met PENDING-intentie vóór de aanvraag, blijvende afstand/routelijn en auditcontext.
Een gewijzigd locatieadres vormt een nieuwe context. HR-correcties blijven
werknemer-specifiek. Oude woon-werkafstanden worden niet verwijderd of aangepast.

Maandshiften heeft aparte groepen en een filter **Meerdere werklocaties**.
Zolang de benodigde tussenafstand ontbreekt staat de extra beweging zonder bedrag.
Mapbox wordt nooit door de controleberekening zelf aangeroepen. Vraag de nieuwe
routes bewust op onder Werknemersroutes; nieuwe Excelcontroles gebruiken daarna
de passende thuis- of tussenlocatieafstand. Geen payroll-export.

Ieder succesvol berekend shiftbedrag kan HR vóór de finale export handmatig
corrigeren. De reden is verplicht; automatisch origineel bedrag, gecorrigeerd
bedrag en volledige correctiehistorie blijven bewaard. Herstellen voegt een
nieuwe historische regel toe en activeert opnieuw de automatische berekening.
Een bedragscorrectie maakt een geblokkeerde of uitgesloten beweging niet
betaalbaar en verandert de bronafstand of vervoerskeuze niet.
