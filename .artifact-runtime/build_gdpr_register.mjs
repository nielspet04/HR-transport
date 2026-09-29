import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/Users/nielspeters/Documents/Codex/2026-09-15/ed/hr-vervoerskosten/outputs/gdpr-register-kilometervergoedingen";
const outputPath = `${outputDir}/GDPR-verwerkingsregister-kilometervergoedingen.xlsx`;
const previewMain = `${outputDir}/preview-register.png`;
const previewGuide = `${outputDir}/preview-toelichting.png`;
const font = "Arial";
const navy = "#17365D";
const blue = "#D9EAF7";
const paleBlue = "#EEF5FA";
const amber = "#FFF2CC";
const red = "#FCE8E6";
const green = "#E2F0D9";
const gray = "#6B7280";
const lightGray = "#E5E7EB";

const workbook = Workbook.create();
const register = workbook.worksheets.add("Verwerkingsregister");
const guide = workbook.worksheets.add("Toelichting & bronnen");

register.showGridLines = false;
guide.showGridLines = false;
register.tabColor = navy;
guide.tabColor = "#7F8C8D";

// Main register sheet
register.getRange("A2:W2").merge();
register.getRange("A2").values = [["GDPR-verwerkingsregister: kilometervergoedingen"]];
register.getRange("A2:W2").format = {
  font: { name: font, size: 15, bold: true, color: navy },
  verticalAlignment: "center",
};
register.getRange("A3:W3").merge();
register.getRange("A3").values = [["Registeritem voor de berekening en uitbetaling van kilometervergoedingen. Vul de geel gemarkeerde organisatiekeuzes aan en laat HR/DPO de bewaartermijnen en ontvangers bevestigen."]];
register.getRange("A3:W3").format = {
  font: { name: font, size: 10, italic: true, color: gray },
  wrapText: true,
  verticalAlignment: "top",
};
register.getRange("A4:W4").format.borders = { bottom: { style: "thin", color: navy } };

const headers = [[
  "ID",
  "Verwerkingsactiviteit",
  "Verwerkingsverantwoordelijke",
  "Proceseigenaar",
  "Doel van de verwerking",
  "Categorieën betrokkenen",
  "Categorieën persoonsgegevens",
  "Bijzondere of strafrechtelijke gegevens",
  "Rechtsgrond",
  "Bron van de gegevens",
  "Interne ontvangers",
  "Externe ontvangers / verwerkers",
  "Doorgifte buiten EER",
  "Bewaartermijn",
  "Startmoment bewaartermijn",
  "Verwijdering / anonimisering",
  "Systemen / opslaglocaties",
  "Technische en organisatorische beveiligingsmaatregelen",
  "Transparantie en rechten betrokkenen",
  "DPIA-beoordeling",
  "Status",
  "Laatst beoordeeld",
  "Acties / opmerkingen"
]];
register.getRange("A6:W6").values = headers;
register.getRange("A6:W6").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};

const record = [[
  "HR-VERV-001",
  "Berekening en uitbetaling van kilometervergoedingen",
  "[Organisatienaam] – te bevestigen",
  "HR / Payroll – te bevestigen",
  "Vaststellen, controleren, goedkeuren en uitbetalen van kilometervergoedingen aan werknemers. Ondersteunen van loonadministratie, boekhouding, fiscale controle en behandeling van vragen of betwistingen.",
  "Werknemers; indien van toepassing ook voormalige werknemers voor de wettelijke bewaartermijn.",
  "Naam; personeelsnummer; woonadres; werkplaats; datum/periode van de verplaatsing; vertrek- en bestemmingslocatie; afgelegde kilometers; route- of verplaatsingsgegevens; vervoermiddel; toepasselijk tarief; berekend en uitbetaald bedrag; goedkeurings- en betaalstatus. Bankrekeningnummer alleen in het betaal- of loonproces, niet in routeanalyses.",
  "Niet beoogd. Vermijd vrije tekst die gezondheidsgegevens, vakbondslidmaatschap, religie of andere gevoelige informatie kan onthullen. Incidenteel aangetroffen gegevens verwijderen of afschermen.",
  "Noodzakelijk voor uitvoering van de arbeidsrelatie (art. 6, lid 1, b AVG) en voor wettelijke verplichtingen inzake loon-, fiscale en boekhoudkundige administratie (art. 6, lid 1, c AVG). Laat HR/DPO de precieze grondslag per onderdeel bevestigen; gebruik toestemming niet als standaardgrondslag in de arbeidsrelatie.",
  "Werknemer; HR-/personeelssysteem; planning of uurregistratie; werkplaats- en roosterdatabase; goedgekeurde route- of afstandsberekening.",
  "Bevoegde medewerkers van HR/Payroll en Finance; leidinggevende uitsluitend voor noodzakelijke goedkeuring; IT-beheer uitsluitend voor ondersteuning en beveiliging, op need-to-knowbasis.",
  "Sociaal secretariaat of payrollprovider; accountant en auditor; bank of betalingsdienst voor noodzakelijke betaalgegevens; hosting-/cloud- en IT-dienstverleners; belasting- en sociale autoriteiten wanneer wettelijk vereist. Leg verwerkersovereenkomsten en concrete leveranciers vast.",
  "Geen doorgifte buiten de EER beoogd. Controleer locaties van cloud-, support- en back-updiensten. Indien wel: land, ontvanger, doorgiftemechanisme en aanvullende waarborgen documenteren.",
  "Bewijsstukken en gegevens die het uitbetaalde bedrag of belastbaar inkomen onderbouwen: 10 jaar / 10 boekjaren na de betrokken belastbare periode. Actieve stamgegevens: zolang de arbeidsrelatie en afhandeling dit vereisen; daarna uit het actieve systeem verwijderen. Gedetailleerde route- of verplaatsingsgegevens: verwijderen of aggregeren zodra de vergoeding definitief is, tenzij ze deel uitmaken van het fiscale/boekhoudkundige bewijs of nodig zijn voor een lopende betwisting. Bevestig deze differentiatie in het interne bewaarbeleid.",
  "Einde van de belastbare/boekhoudkundige periode waarop de vergoeding betrekking heeft; voor actieve stamgegevens: einde arbeidsrelatie of laatste noodzakelijke afhandeling.",
  "Geautomatiseerde bewaartermijnen waar mogelijk; periodieke opschoning; veilige verwijdering uit productie en back-ups volgens back-upcyclus; aggregatie of anonimisering voor rapportering; legal hold bij geschil of controle documenteren.",
  "HR-/payrollsysteem; toepassing voor kilometerberekening; goedkeuringsworkflow; boekhoudsysteem; beveiligde documentopslag; back-ups. Concrete productnamen, hostingregio's en gegevensstromen toevoegen.",
  "Rolgebaseerde toegang en least privilege; MFA voor beheerders en externe toegang; versleuteling tijdens transport en waar passend in opslag; logging van raadpleging en wijzigingen; periodieke toegangsreview; scheiding van invoer, goedkeuring en betaling; back-ups en hersteltesten; patch- en kwetsbaarheidsbeheer; verwerkersovereenkomsten; dataminimalisatie; beperkte exports; veilige verwijdering; incidentrespons; vertrouwelijkheidsafspraken en opleiding.",
  "Opnemen in de werknemersprivacyverklaring: doeleinden, gegevenscategorieën, grondslagen, ontvangers, bewaartermijnen en rechten. Procedure voor inzage, rectificatie, bezwaar waar van toepassing, beperking en klachten bij de GBA. Correctie van adres, route of kilometers moet mogelijk zijn vóór definitieve betaling.",
  "Voorlopig: waarschijnlijk geen DPIA vereist bij beperkte, niet-stelselmatige routeberekening zonder continue tracking. Herbeoordelen bij GPS-tracking, grootschalige profilering, gedragsmonitoring, nieuwe koppelingen of structurele locatieobservatie.",
  "Concept – te bevestigen",
  new Date("2026-09-29T00:00:00Z"),
  "Vul organisatienaam, proceseigenaar, concrete systemen, leveranciers en hostinglocaties in. Bevestig rechtsgrond, bewaartermijnen, internationale doorgiften en DPIA-screening met HR/DPO. Koppel dit item aan de privacyverklaring en het verwijderingsschema."
]];
register.getRange("A7:W7").values = record;
register.getRange("A7:W7").format = {
  font: { name: font, size: 10, color: "#1F2937" },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#AAB7C4" },
};
register.getRange("V7").format.numberFormat = "dd/mm/yyyy";

// Highlight fields that require organisation-specific confirmation.
for (const address of ["C7", "D7", "L7", "M7", "N7", "Q7", "T7", "U7", "W7"]) {
  register.getRange(address).format.fill = amber;
}
register.getRange("U7").format.font = { name: font, size: 10, bold: true, color: "#9C5700" };
register.getRange("H7").format.fill = paleBlue;

register.getRange("A9:W9").merge();
register.getRange("A9").values = [["Legenda: geel = organisatiekeuze of controle vereist. Blauw = aandachtspunt voor dataminimalisatie. Het register moet worden bijgewerkt wanneer het proces, de leveranciers, systemen of bewaartermijnen wijzigen."]];
register.getRange("A9:W9").format = {
  fill: paleBlue,
  font: { name: font, size: 9, italic: true, color: navy },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#B4C7E7" },
};

register.getRange("A7:A200").dataValidation = { rule: { type: "textLength", operator: "between", formula1: 1, formula2: 40 } };
register.getRange("T7:T200").dataValidation = { rule: { type: "list", values: ["Geen DPIA nodig", "DPIA-screening vereist", "DPIA vereist", "Te bevestigen"] } };
register.getRange("U7:U200").dataValidation = { rule: { type: "list", values: ["Concept – te bevestigen", "Actief", "In herziening", "Beëindigd"] } };
register.getRange("U7:U200").conditionalFormats.add("containsText", { text: "Concept", format: { fill: amber, font: { bold: true, color: "#9C5700" } } });
register.getRange("U7:U200").conditionalFormats.add("containsText", { text: "Actief", format: { fill: green, font: { bold: true, color: "#375623" } } });
register.getRange("U7:U200").conditionalFormats.add("containsText", { text: "Beëindigd", format: { fill: lightGray, font: { color: gray } } });

const table = register.tables.add("A6:W7", true, "VerwerkingsregisterTabel");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
table.showBandedRows = true;

register.freezePanes.freezeRows(6);
register.freezePanes.freezeColumns(2);

const widths = {
  A: 14, B: 28, C: 24, D: 20, E: 46, F: 30, G: 58, H: 43, I: 53, J: 38,
  K: 40, L: 54, M: 38, N: 67, O: 40, P: 46, Q: 43, R: 67, S: 58, T: 52,
  U: 24, V: 15, W: 56,
};
for (const [col, width] of Object.entries(widths)) register.getRange(`${col}:${col}`).format.columnWidth = width;
register.getRange("2:2").format.rowHeight = 26;
register.getRange("3:3").format.rowHeight = 34;
register.getRange("6:6").format.rowHeight = 58;
register.getRange("7:7").format.rowHeight = 190;
register.getRange("9:9").format.rowHeight = 34;

// Guide and sources sheet
guide.getRange("A2:F2").merge();
guide.getRange("A2").values = [["Toelichting, controles en bronnen"]];
guide.getRange("A2:F2").format = { font: { name: font, size: 15, bold: true, color: navy } };
guide.getRange("A3:F3").merge();
guide.getRange("A3").values = [["Gebruik deze punten bij de interne goedkeuring van het registeritem."]];
guide.getRange("A3:F3").format = { font: { name: font, size: 10, italic: true, color: gray } };
guide.getRange("A4:F4").format.borders = { bottom: { style: "thin", color: navy } };

guide.getRange("A6:C6").values = [["Controlepunt", "Wat moet worden bevestigd?", "Verantwoordelijke"]];
guide.getRange("A6:C6").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
guide.getRange("A7:C14").values = [
  ["Verwerkingsverantwoordelijke", "Juridische entiteit en contactgegevens van de organisatie; contactgegevens DPO indien van toepassing.", "Management / DPO"],
  ["Rechtsgrond", "Welke delen noodzakelijk zijn voor de arbeidsovereenkomst en welke onder loon-, fiscale of boekhoudkundige verplichtingen vallen.", "HR / Legal / DPO"],
  ["Bewaartermijn", "Koppel elk gegevensobject aan het bewaarschema. Bevestig dat bewijsstukken onder de fiscale/boekhoudkundige termijn vallen en verwijder ruwe routegegevens eerder waar mogelijk.", "Finance / HR / DPO"],
  ["Ontvangers", "Noem concrete interne rollen, sociaal secretariaat, accountant, bank, hosting- en IT-leveranciers. Controleer verwerkersovereenkomsten.", "HR / Procurement / DPO"],
  ["Internationale doorgifte", "Hosting-, support- en back-uplocaties; doorgiftemechanisme en aanvullende waarborgen indien buiten EER.", "IT / DPO"],
  ["Systemen en datastromen", "Concrete applicaties, exportbestanden, integraties, gedeelde mappen en back-ups.", "IT / Proceseigenaar"],
  ["Beveiliging", "Toegangsmatrix, MFA, logging, versleuteling, exportbeperkingen, hersteltesten, toegangsreviews en verwijderingsprocedure.", "IT Security / DPO"],
  ["DPIA", "Nieuwe beoordeling bij GPS-tracking, continue locatieobservatie, profilering, grootschalige koppelingen of monitoring van werknemers.", "DPO / HR"],
];
guide.getRange("A7:C14").format = {
  font: { name: font, size: 10, color: "#1F2937" },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" }, bottom: { style: "thin", color: "#AAB7C4" } },
};
guide.getRange("B7:B14").format.fill = amber;

guide.getRange("A17:F17").values = [["Bron", "Onderwerp", "Praktische betekenis", "Geraadpleegd", "URL", "Opmerking"]];
guide.getRange("A17:F17").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
guide.getRange("A18:F21").values = [
  ["Belgische Gegevensbeschermingsautoriteit", "Inhoud register van verwerkingsactiviteiten", "Registreer onder meer doeleinden, categorieën betrokkenen en gegevens, ontvangers, doorgiften, bewaartermijnen en algemene beveiligingsmaatregelen.", new Date("2026-09-29T00:00:00Z"), "https://www.dataprotectionauthority.be/professioneel/avg/register-van-verwerkingsactiviteiten/wat-moet-er-in-het-register-staan", "Primaire Belgische toezichthouder"],
  ["FOD Financiën", "Bewaring boekhoudkundige en fiscale stukken", "Documenten die nodig zijn om belastbare inkomsten te bepalen en boekhoudkundige bewijsstukken moeten in beginsel 10 jaar / 10 boekjaren worden bewaard.", new Date("2026-09-29T00:00:00Z"), "https://finances.belgium.be/fr/entreprises/impot_des_societes/comptabilite", "Controleer toepassing op de concrete kilometerregistratie"],
  ["Belgium.be", "Persoonsgegevens en privacy", "Algemene overheidsinformatie over persoonsgegevens en bescherming ervan.", new Date("2026-09-29T00:00:00Z"), "https://www.belgium.be/en/personal_data", "Door gebruiker aangeleverde bron"],
  ["Linklaters Data Protected – Belgium", "Belgisch gegevensbeschermingsrecht", "Aanvullend overzicht van het Belgische gegevensbeschermingskader; gebruik primaire bronnen voor definitieve beslissingen.", new Date("2026-09-29T00:00:00Z"), "https://www.linklaters.com/insights/data-protected/data-protected---belgium", "Door gebruiker aangeleverde secundaire bron"],
];
guide.getRange("A18:F21").format = {
  font: { name: font, size: 10, color: "#1F2937" },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" }, bottom: { style: "thin", color: "#AAB7C4" } },
};
guide.getRange("D18:D21").format.numberFormat = "dd/mm/yyyy";
guide.getRange("A24:F24").merge();
guide.getRange("A24").values = [["Dit bestand is een praktisch conceptregister en geen juridisch advies. De organisatie blijft verantwoordelijk voor de definitieve rechtsgrond, bewaartermijnen, leveranciersinventaris, doorgiften en risicoanalyse."]];
guide.getRange("A24:F24").format = {
  fill: paleBlue,
  font: { name: font, size: 9, italic: true, color: navy },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#B4C7E7" },
};

guide.getRange("A:A").format.columnWidth = 31;
guide.getRange("B:B").format.columnWidth = 72;
guide.getRange("C:C").format.columnWidth = 45;
guide.getRange("D:D").format.columnWidth = 16;
guide.getRange("E:E").format.columnWidth = 64;
guide.getRange("F:F").format.columnWidth = 42;
guide.getRange("6:6").format.rowHeight = 34;
guide.getRange("7:14").format.rowHeight = 52;
guide.getRange("17:17").format.rowHeight = 34;
guide.getRange("18:21").format.rowHeight = 76;
guide.getRange("24:24").format.rowHeight = 42;
guide.freezePanes.freezeRows(6);

// Consistent font and alignment in intentionally populated areas.
register.getRange("A2:W9").format.font.name = font;
guide.getRange("A2:F24").format.font.name = font;

workbook.recalculate();

const mainCheck = await workbook.inspect({
  kind: "table",
  range: "Verwerkingsregister!A2:W9",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 23,
  maxChars: 9000,
});
console.log("MAIN_CHECK");
console.log(mainCheck.ndjson);

const sourceCheck = await workbook.inspect({
  kind: "table",
  range: "'Toelichting & bronnen'!A17:F24",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 6,
  maxChars: 6000,
});
console.log("SOURCE_CHECK");
console.log(sourceCheck.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log("ERROR_SCAN");
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const mainPreviewBlob = await workbook.render({ sheetName: "Verwerkingsregister", range: "A1:W9", scale: 0.8, format: "png" });
await fs.writeFile(previewMain, new Uint8Array(await mainPreviewBlob.arrayBuffer()));
const guidePreviewBlob = await workbook.render({ sheetName: "Toelichting & bronnen", range: "A1:F24", scale: 1, format: "png" });
await fs.writeFile(previewGuide, new Uint8Array(await guidePreviewBlob.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT=${outputPath}`);
console.log(`PREVIEW_MAIN=${previewMain}`);
console.log(`PREVIEW_GUIDE=${previewGuide}`);
