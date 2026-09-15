from openpyxl import Workbook

from scripts.inspect_sources import (
    PERFORMANCE_HEADERS,
    detect_header_row,
    normalized_text,
    print_safe_counts,
)


def test_header_detection_skips_intro_rows() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Rapporttitel"])
    sheet.append(list(PERFORMANCE_HEADERS))

    row_number, headers = detect_header_row(sheet, PERFORMANCE_HEADERS)

    assert row_number == 2
    assert set(headers) == PERFORMANCE_HEADERS


def test_normalized_text_keeps_missing_values_missing() -> None:
    assert normalized_text(None) == ""
    assert normalized_text("  PostNL   Willebroek ") == "postnl willebroek"


def test_unexpected_category_content_is_suppressed(capsys) -> None:
    unexpected_sensitive_value = "persoon@example.test"

    print_safe_counts(
        "Woon-werkvervoer uitbetalen",
        ["Wel uitbetalen", unexpected_sensitive_value],
    )

    output = capsys.readouterr().out
    assert "Wel uitbetalen" in output
    assert "<overig/onverwacht; inhoud onderdrukt>" in output
    assert unexpected_sensitive_value not in output

