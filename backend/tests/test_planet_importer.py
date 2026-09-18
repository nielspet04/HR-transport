"""Only fictional fixtures; temporary XLSX files use minimal standard OOXML."""

from datetime import date, datetime, time
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile

import pytest

from app.importers.planet import (
    HEADERS, FieldError, ImportSourceError, import_planet, parse_day, parse_kms, parse_time,
)


def write_xlsx(path: Path, rows: list[list], *, sheet_name: str = "Total kms", dimension: str | None = None) -> Path:
    """Create tiny fictitious test input, not a user-facing workbook."""
    sheet_rows = []
    for row_number, values in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(values):
            column = ""
            remaining = index + 1
            while remaining:
                remaining, letter = divmod(remaining - 1, 26)
                column = chr(65 + letter) + column
            address = f"{column}{row_number}"
            if value is None:
                continue
            if isinstance(value, dict):
                if "formula" in value:
                    cells.append(f'<c r="{address}"><f>{escape(value["formula"])}</f></c>')
                else:
                    cells.append(f'<c r="{address}" t="e"><v>{escape(value["error"])}</v></c>')
            elif isinstance(value, bool):
                cells.append(f'<c r="{address}" t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{address}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name={quoteattr(sheet_name)} sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        dimension_xml = f'<dimension ref={quoteattr(dimension)}/>' if dimension else ""
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{dimension_xml}<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    return path


def fictional_row(**changes) -> list:
    values = dict(zip(HEADERS, [
        "006", "Voorbeeld", "Alex", "Afdeling", "2026-08-01", "Testtaak",
        "05:30", "13:00", None, "TESTLOCATIE", 17.5,
    ]))
    values.update(changes)
    return [values[header] for header in HEADERS]


def test_valid_import_preserves_types_provenance_and_source(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row()])
    before = sha256(path.read_bytes()).hexdigest()
    result = import_planet(path)
    shift = result.shifts[0]
    assert shift.employee_id == "006"
    assert shift.day == date(2026, 8, 1)
    assert shift.start_time == time(5, 30)
    assert shift.kms == Decimal("17.5")
    assert shift.source_row == 2
    assert shift.source_sheet == "Total kms"
    assert shift.source_file == "fictional.xlsx"
    assert result.report.source_sha256 == before == sha256(path.read_bytes()).hexdigest()
    assert not result.has_errors


def test_intro_blank_summary_and_repeated_header_are_accounted(tmp_path):
    summary = ["006 Total"] + [None] * 9 + [{"formula": "SUM(K4:K4)"}]
    path = write_xlsx(tmp_path / "fictional.xlsx", [
        ["Rapporttitel"], list(HEADERS), [], fictional_row(), summary,
        list(HEADERS), fictional_row(),
    ])
    result = import_planet(path)
    report = result.report
    assert report.header_row == 2
    assert report.data_rows_seen == 5
    assert report.blank_rows == report.summary_rows == report.repeated_header_rows == 1
    assert report.imported_rows == 2
    assert report.rejected_rows == 0


@pytest.mark.parametrize("field", ["Id", "Last name", "First name", "Day", "Task", "Debut tache", "Fin tache", "Customer"])
def test_missing_required_value_is_visible(tmp_path, field):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(**{field: None})])
    result = import_planet(path)
    assert result.has_errors
    assert result.report.rejected_rows == 1
    assert len(result.shifts) == 0
    assert any(issue.code == "MISSING_VALUE" and issue.field == field for issue in result.issues)


def test_optional_blanks_remain_none_not_zero(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(**{"Department": None, "Kms": None})])
    result = import_planet(path)
    assert result.shifts[0].department is None
    assert result.shifts[0].remark is None
    assert result.shifts[0].kms is None
    assert any(issue.code == "MISSING_KMS" for issue in result.issues)
    assert not result.has_errors


def test_no_cleaning_matching_or_remark_rules(tmp_path):
    rows = [fictional_row(Remark=value) for value in ["Telework", "48h_ICTS_Extra_Shift", "Nieuwe onbekende code"]]
    rows += [fictional_row(Customer="ANDERE LOCATIE")]
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), *rows]))
    assert len(result.shifts) == 4
    assert [shift.remark for shift in result.shifts[:3]] == ["Telework", "48h_ICTS_Extra_Shift", "Nieuwe onbekende code"]


def test_multiple_months_no_silent_selection(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(), fictional_row(Day="2026-07-31")])
    all_months = import_planet(path)
    august = import_planet(path, month="2026-08")
    assert len(all_months.shifts) == 2
    assert all_months.report.months == ("2026-07", "2026-08")
    assert any(issue.code == "MULTIPLE_MONTHS" for issue in all_months.issues)
    assert august.report.imported_rows == august.report.outside_month_rows == 1
    assert august.shifts[0].day.month == 8
    missing_month = import_planet(path, month="2026-06")
    assert missing_month.has_errors
    assert missing_month.report.imported_rows == 0


def test_invalid_row_outside_month_still_visible(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(), fictional_row(Day="2026-07-31", **{"Fin tache": "wrong"})])
    result = import_planet(path, month="2026-08")
    assert result.has_errors
    assert result.report.imported_rows == result.report.rejected_rows == 1


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "08-2026", "2026-8", "2026-08-01", "0000-01"])
def test_invalid_month_rejected_before_reading(month):
    with pytest.raises(ImportSourceError):
        import_planet("does-not-exist.xlsx", month=month)


@pytest.mark.parametrize("value", ["2026-02-30", "01/08/2026", "2026-8-1", 46235, True, None, "=TODAY()"])
def test_date_parser_rejects_invalid_or_ambiguous_values(value):
    with pytest.raises(FieldError):
        parse_day(value)


@pytest.mark.parametrize("value", [date(2026, 8, 1), datetime(2026, 8, 1), "2026-08-01"])
def test_date_parser_accepts_explicit_dates(value):
    assert parse_day(value) == date(2026, 8, 1)


def test_day_with_non_midnight_time_rejected():
    with pytest.raises(FieldError, match="DATE_CONTAINS_TIME"):
        parse_day(datetime(2026, 8, 1, 12))


@pytest.mark.parametrize("value", ["24:00", "05:60", "5:30", 0.5, None, "=NOW()"])
def test_time_parser_rejects_ambiguous_values(value):
    with pytest.raises(FieldError):
        parse_time(value)


@pytest.mark.parametrize("value", ["05:30", "05:30:00", time(5, 30)])
def test_time_parser_accepts_explicit_times(value):
    assert parse_time(value) == time(5, 30)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "1,234.5", "unknown", "=SUM(K2:K3)"])
def test_kms_invalid_values_not_zero(value):
    with pytest.raises(FieldError):
        parse_kms(value)


@pytest.mark.parametrize("value,expected", [(0, "0"), (17.5, "17.5"), ("17,5", "17.5"), ("17.5", "17.5"), (-2, "-2")])
def test_kms_numeric_values(value, expected):
    assert parse_kms(value) == Decimal(expected)


def test_night_and_equal_time_warn_without_inferred_date(tmp_path):
    rows = [fictional_row(**{"Debut tache": "22:30", "Fin tache": "05:30"}), fictional_row(**{"Fin tache": "05:30"})]
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), *rows]))
    assert result.report.imported_rows == 2
    assert {issue.code for issue in result.issues} == {"END_BEFORE_START", "SAME_START_END_TIME"}
    assert result.shifts[0].day == date(2026, 8, 1)


def test_numeric_id_not_silently_padded(tmp_path):
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(Id=6)]))
    assert result.has_errors
    assert result.issues[0].code == "INVALID_IDENTIFIER_TYPE"


@pytest.mark.parametrize("end_value", ["24:00", "24:00:00"])
def test_explicit_end_midnight_preserves_next_day_offset(tmp_path, end_value):
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(**{"Fin tache": end_value})]))
    assert not result.has_errors
    assert result.shifts[0].end_time == time(0)
    assert result.shifts[0].end_time_day_offset == 1
    assert [issue.code for issue in result.issues] == ["EXPLICIT_24H_END"]


def test_formula_or_excel_error_in_core_field_rejected(tmp_path):
    rows = [fictional_row(Remark={"formula": '"Telework"'}), fictional_row(Customer={"error": "#N/A"})]
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), *rows]))
    assert result.report.rejected_rows == 2
    assert {issue.code for issue in result.issues} == {"FORMULA_NOT_SUPPORTED", "SOURCE_CELL_ERROR"}


def test_total_marker_with_shift_data_not_discarded_silently(tmp_path):
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(Id="006 Total")]))
    assert result.report.summary_rows == 0
    assert result.report.rejected_rows == 1
    assert result.issues[0].code == "AMBIGUOUS_SUMMARY_ROW"


def test_headers_reordered_normalized_and_extra_named_columns(tmp_path):
    headers = [f" {header.upper()} " for header in reversed(HEADERS)] + ["Extra veld"]
    values = list(reversed(fictional_row())) + ["Geen kernveld"]
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [headers, values]))
    assert result.report.imported_rows == 1
    assert result.shifts[0].employee_id == "006"
    assert result.issues[0].code == "EXTRA_COLUMNS_IGNORED"


def test_unheaded_nonempty_data_not_dropped(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS) + [None], fictional_row() + ["unheaded"]])
    result = import_planet(path)
    assert result.report.rejected_rows == 1
    assert result.issues[0].code == "UNHEADED_DATA"


@pytest.mark.parametrize("headers", [list(HEADERS[:-1]), list(HEADERS) + ["Id"]])
def test_missing_or_duplicate_headers_fail(tmp_path, headers):
    with pytest.raises(ImportSourceError):
        import_planet(write_xlsx(tmp_path / "fictional.xlsx", [headers, fictional_row()]))


def test_wrong_sheet_fails(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS)], sheet_name="Wrong sheet")
    with pytest.raises(ImportSourceError, match="werkblad"):
        import_planet(path)


def test_empty_valid_source_is_accounted(tmp_path):
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS)]))
    assert result.report.imported_rows == result.report.data_rows_seen == 0


def test_completely_empty_sheet_fails_visibly(tmp_path):
    with pytest.raises(ImportSourceError):
        import_planet(write_xlsx(tmp_path / "fictional.xlsx", []))


def test_corrupt_source_fails_without_exposing_values(tmp_path):
    path = tmp_path / "fictional.xlsx"
    path.write_bytes(b"not an Excel file")
    with pytest.raises(ImportSourceError, match="niet worden geopend"):
        import_planet(path)


def test_model_repr_does_not_expose_identity_or_location(tmp_path):
    result = import_planet(write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row()]))
    text = repr(result) + repr(result.shifts[0])
    assert "Voorbeeld" not in text
    assert "Alex" not in text
    assert "TESTLOCATIE" not in text


def test_understated_dimension_does_not_truncate_source(tmp_path):
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), fictional_row(), fictional_row()], dimension="A1:K2")
    result = import_planet(path)
    assert result.report.imported_rows == result.report.data_rows_seen == 2


@pytest.mark.parametrize("bad_row,exit_code", [(False, 0), (True, 1)])
def test_cli_reports_counts_without_person_values(tmp_path, bad_row, exit_code):
    row = fictional_row(**{"Fin tache": "invalid"}) if bad_row else fictional_row(Remark="persoon@example.test")
    path = write_xlsx(tmp_path / "fictional.xlsx", [list(HEADERS), row])
    cli = Path(__file__).resolve().parents[2] / "scripts" / "import_planet.py"
    completed = subprocess.run([sys.executable, str(cli), str(path)], capture_output=True, text=True)
    assert completed.returncode == exit_code
    assert "Geïmporteerde shifts:" in completed.stdout
    for sensitive in ("Voorbeeld", "Alex", "TESTLOCATIE", "persoon@example.test"):
        assert sensitive not in completed.stdout + completed.stderr
