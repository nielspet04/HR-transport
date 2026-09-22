# Nieuwe klant uit een Pl@net-export

Een onbekende klant of fysieke werklocatie blijft zichtbaar in de
volledigheidscontrole. Het dashboard toont daar één formulier per onbekende
bronlocatie.

HR kiest één van twee mogelijkheden:

- de klant hoort bij een bestaande fysieke locatie;
- de klant is een nieuwe fysieke locatie, waarvoor naam, adres en ingangsdatum
  worden ingevuld.

Na bevestiging bewaart één database-transactie de klantkoppeling en, indien
nodig, het nieuwe gedateerde locatieadres. Voor reeds gekoppelde werknemers met
shiften op deze klant wordt standaard `Privé auto` vastgelegd. De volledige
bronexport wordt opnieuw verwerkt. Daarna vraagt de bestaande automatische
Mapbox-flow de locatiecoördinaten en alleen de benodigde routes op.

Een nog onbekende werknemer en een nieuwe klant kunnen tegelijk in een export
staan. De klant kan eerst worden geregistreerd; de werknemer blijft zichtbaar
tot diens eigen onboardingformulier is voltooid. Geen van beide kan stil uit de
maandberekening verdwijnen.

Als één invoer ongeldig is, worden klantkoppeling, locatieadres en routes samen
teruggedraaid. Een werkelijk nieuwe locatie krijgt nooit stilzwijgend het adres
of de afstand van een bestaande locatie.
