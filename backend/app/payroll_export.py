"""Replace example rows in the fixed official Accerta template with one closed month."""
from calendar import monthrange
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from posixpath import normpath
import re
from xml.etree import ElementTree
from xml.sax.saxutils import escape
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter
from openpyxl.utils.datetime import to_excel


SHEET = 'Afwijkende loonelementen'
REMOVED_SHEET = 'LIST NIET UITBETALEN '
HEADERS = (
    'Acerta Connect\nStandaard Template\n Afwijkende loonelementen\n(*) verplicht',
    'Update code',
    'Extern referentienummer (type HRM-nummer) (*)',
    'Naam werknemer',
    'Loonperiode (*)',
    'Manipulatiecode',
    'Looncode (*)',
    'Eenheden',
    'Bedrag per eenheid',
    'Percentage',
    'Bedrag',
    'Dagen',
    'Kostenplaats',
    'Reden',
    'Startdatum (fractie)',
    'Einddatum (fractie)',
)
PAY_CODES = {'STANDARD': '25', 'SPECIAL': '26', 'EXTRA48': '4864', 'BICYCLE': '420'}
EXCLUDED = {'EXCLUDED_TRAIN', 'EXCLUDED_COMPANY_CAR', 'EXCLUDED_MOBILITY_BUDGET', 'EXCLUDED_TELEWORK'}


def _amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Een berekend shiftbedrag is ongeldig.') from None
    if not result.is_finite() or result < 0 or result > Decimal('100000'):
        raise ValueError('Een berekend shiftbedrag valt buiten het toegestane bereik.')
    if result != result.quantize(Decimal('.01')):
        raise ValueError('Een berekend shiftbedrag heeft meer dan twee decimalen.')
    return result


def payroll_rows(payload):
    """Group every paid movement by worker, location, pay code and exact amount."""
    calculation = payload.get('calculation') or {}
    monthly = calculation.get('monthly') or {}
    if payload.get('stale'):
        raise ValueError('Vernieuw deze maand eerst; de instellingen zijn intussen gewijzigd.')
    if not monthly or not monthly.get('ready'):
        raise ValueError('Los eerst alle berekeningsblokkeringen van deze maand op.')
    if not monthly.get('external_references_ready'):
        raise ValueError('Iedere werknemer moet de hele maand één geldig extern loonnummer hebben.')
    try:
        year, month = (int(part) for part in payload['month'].split('-'))
        period = date(year, month, 1)
    except (KeyError, ValueError, AttributeError):
        raise ValueError('De geselecteerde loonmaand is ongeldig.') from None
    end = date(year, month, monthrange(year, month)[1])
    movements = {movement['id']: movement for movement in payload.get('movements', [])}
    agents = {agent['planet_id']: agent for agent in payload.get('agents', [])}
    employees = {employee['worker_id']: employee for employee in monthly.get('employees', [])}
    groups = Counter()
    calculated_total = Decimal('0')
    calculated_count = 0
    for result in calculation.get('rows', []):
        status = result.get('status')
        if status in EXCLUDED:
            continue
        if status != 'CALCULATED':
            raise ValueError('Niet iedere beweging is berekend of terecht uitgesloten.')
        movement = movements.get(result.get('movement_id'))
        if not movement:
            raise ValueError('Een berekende beweging ontbreekt in de maandbron.')
        agent = agents.get(movement.get('planet_id'))
        worker_id = agent and agent.get('worker_id')
        employee = employees.get(worker_id)
        if not employee or employee.get('external_reference_status') != 'READY':
            raise ValueError('Een berekende werknemer heeft geen eenduidig loonnummer voor deze maand.')
        kind = result.get('tariff_kind')
        code = PAY_CODES.get(kind)
        if not code:
            raise ValueError('Onbekende vergoedingssoort; export gestopt om een verkeerde looncode te voorkomen.')
        amount = _amount(result.get('amount'))
        location = str(movement.get('location') or movement.get('source_location') or '').strip()
        if not location:
            raise ValueError('Een berekende shift heeft geen fysieke locatie.')
        key = (worker_id, employee['external_reference'], employee['name'], code, location, amount)
        groups[key] += 1
        calculated_total += amount
        calculated_count += 1
    if not calculated_count:
        raise ValueError('Deze maand bevat geen vergoedbare shiften om te exporteren.')
    rows = []
    order = {'25': 0, '26': 1, '4864': 2, '420': 3}
    for (_, reference, name, code, location, amount), units in sorted(
        groups.items(), key=lambda item: (item[0][2].casefold(), order[item[0][3]], item[0][4].casefold(), item[0][5])
    ):
        rows.append([None, 'c', reference, str(name), period, None, code, units, float(amount),
                     None, None, None, None, location, period, end])
    grouped_total = sum((Decimal(str(row[7])) * Decimal(str(row[8])) for row in rows), Decimal('0'))
    expected = _amount(monthly.get('calculated_total'))
    if calculated_total != expected or grouped_total != expected:
        raise ValueError('Exportcontrole mislukt: de gegroepeerde regels sluiten niet aan op het maandtotaal.')
    return rows


def _safe_workbook(content):
    if not isinstance(content, bytes) or not content or len(content) > 5_000_000:
        raise ValueError('Kies het officiële Accerta-.xlsx-bestand van maximaal 5 MB.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(item.file_size for item in entries) > 64_000_000:
                raise ValueError('Het Accerta-bestand bevat te veel uitgepakte gegevens.')
    except BadZipFile:
        raise ValueError('Het gekozen bestand is geen geldige .xlsx-werkmap.') from None
    try:
        workbook = load_workbook(BytesIO(content), data_only=False, keep_links=True)
    except Exception:
        raise ValueError('Het gekozen Accerta-bestand kan niet veilig worden gelezen.') from None
    if workbook.sheetnames != [SHEET, REMOVED_SHEET]:
        workbook.close()
        raise ValueError('Dit is niet het verwachte officiële Accerta-bestand: tabbladen wijken af.')
    sheet = workbook[SHEET]
    actual = tuple(sheet.cell(1, column).value for column in range(1, 17))
    if actual != HEADERS or sheet.max_column != 16 or sheet.max_row < 2:
        workbook.close()
        raise ValueError('Dit is niet het verwachte officiële Accerta-bestand: kolomstructuur wijkt af.')
    return workbook


def _remove_informational_sheet(source):
    """Remove the non-payable-list sheet and its package references."""
    workbook_path = 'xl/workbook.xml'
    relationships_path = 'xl/_rels/workbook.xml.rels'
    content_types_path = '[Content_Types].xml'
    workbook = ElementTree.fromstring(source.read(workbook_path))
    namespace = workbook.tag.partition('}')[0] + '}'
    sheets = workbook.find(namespace + 'sheets')
    relation_key = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    matches = [sheet for sheet in sheets if sheet.attrib.get('name') == REMOVED_SHEET]
    if len(matches) != 1 or not matches[0].attrib.get(relation_key):
        raise ValueError('Het informatieve Accerta-tabblad kan niet veilig worden verwijderd.')
    removed = matches[0]
    relation_id = removed.attrib[relation_key]
    sheets.remove(removed)

    defined_names = workbook.find(namespace + 'definedNames')
    if defined_names is not None:
        for defined_name in list(defined_names):
            if defined_name.attrib.get('localSheetId') == '1' or REMOVED_SHEET.strip() in (defined_name.text or ''):
                defined_names.remove(defined_name)
        if not list(defined_names):
            workbook.remove(defined_names)

    relationships = ElementTree.fromstring(source.read(relationships_path))
    related = [item for item in relationships if item.attrib.get('Id') == relation_id]
    if len(related) != 1:
        raise ValueError('De verwijzing naar het informatieve Accerta-tabblad is niet eenduidig.')
    target = related[0].attrib.get('Target', '')
    relationships.remove(related[0])
    sheet_path = normpath(target.lstrip('/') if target.startswith('/xl/') else f'xl/{target}')
    if not sheet_path.startswith('xl/worksheets/') or sheet_path not in source.namelist():
        raise ValueError('Het informatieve Accerta-tabblad heeft een onverwachte pakketstructuur.')

    content_types = ElementTree.fromstring(source.read(content_types_path))
    overrides = [item for item in content_types if item.attrib.get('PartName') == f'/{sheet_path}']
    if len(overrides) != 1:
        raise ValueError('Het informatieve Accerta-tabblad heeft geen eenduidig inhoudstype.')
    content_types.remove(overrides[0])
    removed_parts = {sheet_path, f"{sheet_path.rsplit('/', 1)[0]}/_rels/{sheet_path.rsplit('/', 1)[1]}.rels"}
    replacements = {
        workbook_path: ElementTree.tostring(workbook, encoding='utf-8', xml_declaration=True),
        relationships_path: ElementTree.tostring(relationships, encoding='utf-8', xml_declaration=True),
        content_types_path: ElementTree.tostring(content_types, encoding='utf-8', xml_declaration=True),
    }
    return removed_parts, replacements


def _row_xml(number, values, row_start, styles, present):
    opening = re.sub(rb'\br="\d+"', f'r="{number}"'.encode(), row_start, count=1).decode()
    cells = []
    for column, value in enumerate(values, 1):
        if value is None and column not in present:
            continue
        coordinate = f'{get_column_letter(column)}{number}'
        style = f' s="{styles[column]}"' if column in styles else ''
        if value is None:
            cells.append(f'<c r="{coordinate}"{style}/>')
        elif isinstance(value, date):
            cells.append(f'<c r="{coordinate}"{style}><v>{to_excel(value):g}</v></c>')
        elif isinstance(value, bool):
            raise ValueError('Booleaanse waarden zijn niet toegestaan in de Accerta-export.')
        elif isinstance(value, (int, float, Decimal)):
            cells.append(f'<c r="{coordinate}"{style}><v>{value}</v></c>')
        else:
            text = escape(str(value))
            preserve = ' xml:space="preserve"' if text != text.strip() else ''
            cells.append(f'<c r="{coordinate}"{style} t="inlineStr"><is><t{preserve}>{text}</t></is></c>')
    return (opening + ''.join(cells) + '</row>').encode()


def replace_example_rows(template, rows):
    """Replace all example rows while preserving every other OOXML part byte-for-byte."""
    workbook = _safe_workbook(template)
    sheet = workbook[SHEET]
    style_row = sheet.max_row
    workbook.close()
    with ZipFile(BytesIO(template)) as source:
        xml = source.read('xl/worksheets/sheet1.xml')
        root = ElementTree.fromstring(xml)
        namespace = root.tag.partition('}')[0] + '}'
        sheet_data = root.find(namespace + 'sheetData')
        template_row = next((row for row in reversed(list(sheet_data)) if int(row.attrib['r']) == style_row), None)
        if template_row is None:
            raise ValueError('De laatste officiële Accerta-voorbeeldregel ontbreekt.')
        styles = {}; present = set()
        for cell in template_row:
            reference = cell.attrib.get('r', '')
            match = re.match(r'([A-Z]+)', reference)
            if not match:
                continue
            column = 0
            for letter in match.group(1):
                column = column * 26 + ord(letter) - 64
            present.add(column)
            if 's' in cell.attrib:
                styles[column] = cell.attrib['s']
        row_matches = list(re.finditer(rb'<row\b[^>]*\br="' + str(style_row).encode() + rb'"[^>]*>', xml))
        if len(row_matches) != 1:
            raise ValueError('De laatste officiële Accerta-voorbeeldregel is niet eenduidig.')
        row_start = row_matches[0].group(0)
        additions = b''.join(_row_xml(index, values, row_start, styles, present)
                             for index, values in enumerate(rows, 2))
        if xml.count(b'</sheetData>') != 1:
            raise ValueError('De Accerta-werkbladstructuur is niet eenduidig.')
        header = re.search(rb'<row\b[^>]*\br="1"[^>]*>.*?</row>', xml, re.DOTALL)
        sheet_data_end = xml.find(b'</sheetData>')
        if not header or sheet_data_end < header.end():
            raise ValueError('De Accerta-headerstructuur is niet eenduidig.')
        last_row = 1 + len(rows)
        xml = xml[:header.end()] + additions + xml[sheet_data_end:]
        xml, dimensions = re.subn(rb'<dimension ref="A1:P\d+"\s*/>', f'<dimension ref="A1:P{last_row}"/>'.encode(), xml, count=1)
        xml, filters = re.subn(rb'(<autoFilter\b[^>]*\bref=")A1:XFD\d+("[^>]*>)', rb'\g<1>A1:XFD' + str(last_row).encode() + rb'\g<2>', xml, count=1)
        if dimensions != 1 or filters != 1:
            raise ValueError('Bereik of filter van het officiële Accerta-werkblad wijkt af.')
        output = BytesIO()
        removed_parts, replacements = _remove_informational_sheet(source)
        replacements['xl/worksheets/sheet1.xml'] = xml
        with ZipFile(output, 'w', ZIP_DEFLATED) as target:
            for info in source.infolist():
                if info.filename in removed_parts:
                    continue
                target.writestr(info, replacements.get(info.filename, source.read(info.filename)))
    return output.getvalue()


def workbook_bytes(store, run_id):
    if type(run_id) is not int:
        raise ValueError('Selecteer een maandverwerking.')
    template_path = store.path.parent / 'acerta-template.xlsx'
    if not template_path.is_file():
        raise ValueError('Het vaste Accerta-sjabloon ontbreekt in de lokale gegevensmap.')
    payload = store.get_matching(run_id)
    return replace_example_rows(template_path.read_bytes(), payroll_rows(payload)), payload['month']
