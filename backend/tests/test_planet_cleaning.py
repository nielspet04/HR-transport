"""Synthetic phase-2 tests: no real employee records in fixtures."""

from dataclasses import replace
from datetime import date, time
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.cleaning import CleaningPolicy, clean_import
from app.importers.planet import HEADERS, import_planet
from app.models.shift import ImportIssue, ImportReport, ImportResult, Shift


def shift(row=2, **changes):
    base = Shift("006", "Voorbeeld", "Alex", None, date(2026, 8, 1),
                 "Test", time(8), time(16), None, None, "TESTLOCATIE",
                 Decimal("10"), "fictional.xlsx", "Total kms", row)
    return replace(base, **changes)


def imported(*rows, month="2026-08"):
    report = ImportReport(1, len(rows), 0, 0, 0, 0, len(rows), 0,
                          ("2026-08",), month, "synthetic")
    return ImportResult(tuple(rows), (), report)


def test_filters_before_grouping_and_preserves_all_evidence():
    rows = (shift(2, remark=" TeleWork "), shift(3),
            shift(4, remark="48h_ICTS_Extra_Shift", kms=Decimal("20")),
            shift(5, customer="ANDERELOCATIE"), shift(6, employee_id="007"),
            shift(7, day=date(2026, 8, 2)))
    result = clean_import(imported(*rows))
    assert result.report.input_rows == 6
    assert result.report.telework_rows == 1
    assert result.report.duplicate_rows == 1
    assert result.report.remaining_movements == 4
    assert result.movements[0].source_shifts == rows[1:3]
    assert result.unresolved_shifts == (rows[2],)
    assert [r.reason for r in result.removals] == ["TELEWORK", "DUPLICATE_MOVEMENT"]


def test_no_guessed_absences_or_substring_filtering():
    rows = tuple(shift(i+2, day=date(2026, 8, i+1), remark=remark)
                 for i, remark in enumerate(("Administration", "Wissel", "Telework extra", "OV_DL")))
    result = clean_import(imported(*rows))
    assert result.report.remaining_movements == 4
    assert result.report.unresolved_remark_rows == 4


def test_explicit_exclusions_and_policy_snapshot():
    policy = CleaningPolicy((" CONFIRMED_ABSENCE ", "confirmed_absence"))
    result = clean_import(imported(shift(remark="Confirmed_Absence")), policy=policy)
    assert result.report.excluded_remark_rows == 1
    assert result.report.remaining_movements == 0
    assert result.policy.excluded_remarks == ("confirmed_absence",)
    with pytest.raises(ValueError):
        CleaningPolicy((" ",))


def test_error_import_and_month_leak_refused():
    source = imported(shift())
    with pytest.raises(ValueError, match="import errors"):
        clean_import(replace(source, issues=(ImportIssue("TEST", "ERROR"),)))
    with pytest.raises(ValueError, match="outside selected month"):
        clean_import(imported(shift(day=date(2026, 7, 1))))


def test_empty_and_all_months_accounting():
    assert clean_import(imported()).report.remaining_movements == 0
    result = clean_import(imported(shift(), shift(3, day=date(2026, 7, 1)), month=None))
    r = result.report
    assert r.input_rows == r.ghost_agent_rows + r.telework_rows + r.excluded_remark_rows + r.duplicate_rows + r.remaining_movements
    assert r.remaining_movements == 2


def test_customer_case_not_fuzzy_matched():
    result = clean_import(imported(shift(), shift(3, customer="testlocatie")))
    assert result.report.remaining_movements == 2


def test_month_selection_before_cleaning(tmp_path):
    from test_planet_importer import fictional_row, write_xlsx
    path = tmp_path / "fictional.xlsx"
    write_xlsx(path, [list(HEADERS),
                      fictional_row(Day="2026-07-01", Remark="Telework"),
                      fictional_row(), fictional_row(Remark="48h_ICTS_Extra_Shift")])
    source = import_planet(path, month="2026-08")
    result = clean_import(source)
    assert source.report.outside_month_rows == 1
    assert result.report.input_rows == 2
    assert result.report.telework_rows == 0
    assert result.report.duplicate_rows == 1


def test_cli_requires_explicit_scope():
    root = Path(__file__).resolve().parents[2]
    process = subprocess.run([sys.executable, str(root / "scripts/clean_planet.py"), "fictional.xlsx"],
                             capture_output=True, text=True)
    assert process.returncode == 2
    assert "--month" in process.stderr


@pytest.mark.parametrize("employee_id", ["1112", "1113", "1114", "1115", "1116"])
def test_all_confirmed_ghost_agents_excluded_before_other_rules(employee_id):
    source = imported(shift(employee_id=employee_id, remark="Telework"),
                      shift(3, employee_id=employee_id, remark="48h_ICTS_Extra_Shift"),
                      shift(4), shift(5))
    result = clean_import(source)
    assert result.report.ghost_agent_rows == 2
    assert result.report.telework_rows == 0
    assert result.report.duplicate_rows == 1
    assert result.report.remaining_movements == 1
    assert result.unresolved_shifts == ()
    assert [r.reason for r in result.removals] == ["GHOST_AGENT", "GHOST_AGENT", "DUPLICATE_MOVEMENT"]
    assert all(s.employee_id != employee_id for m in result.movements for s in m.source_shifts)
    r = result.report
    assert r.input_rows == r.ghost_agent_rows + r.telework_rows + r.excluded_remark_rows + r.duplicate_rows + r.remaining_movements


def test_ghost_ids_exact_match_and_centrally_configurable():
    source = imported(*(shift(i+2, employee_id=value) for i,value in enumerate(
        ("1112", "01112", "11120", "1111", "1117"))))
    assert clean_import(source).report.ghost_agent_rows == 1
    assert clean_import(source, policy=CleaningPolicy(ghost_employee_ids=())).report.ghost_agent_rows == 0
    policy = CleaningPolicy(ghost_employee_ids=(" 1112 ", "1112", "1117"))
    assert policy.ghost_employee_ids == ("1112", "1117")
    assert clean_import(source, policy=policy).report.ghost_agent_rows == 2
    with pytest.raises(ValueError):
        CleaningPolicy(ghost_employee_ids=(1112,))


def test_ghost_shifts_only_in_selected_month(tmp_path):
    from test_planet_importer import fictional_row, write_xlsx
    source = write_xlsx(tmp_path / "ghosts.xlsx", [list(HEADERS),
        fictional_row(Id="1112", Day="2026-07-01"),
        fictional_row(Id="1112"), fictional_row()])
    result = clean_import(import_planet(source, month="2026-08"))
    assert result.report.input_rows == 2
    assert result.report.ghost_agent_rows == 1
    assert result.report.remaining_movements == 1


def test_confirmed_airport_customers_one_movement_despite_time_gaps():
    rows = tuple(shift(i+2, customer=customer, start_time=time(7+i*3),
                       remark="48h_ICTS_Extra_Shift" if i == 3 else None)
                 for i,customer in enumerate(("DELTA AIRLINES", "HAINAN AIRLINES", "LATAM CARGO", "TUI")))
    result = clean_import(imported(*rows))
    assert result.report.duplicate_rows == 3
    assert result.report.remaining_movements == 1
    assert result.movements[0].physical_location == "LUCHTHAVEN"
    assert result.movements[0].source_shifts == rows
    assert result.unresolved_shifts == (rows[3],)
    assert [r.shift.source_row for r in result.removals] == [3, 4, 5]


def test_airport_does_not_merge_other_workers_days_or_unknown_customers():
    result = clean_import(imported(shift(customer=" delta airlines "),
        shift(3,customer="hainan airlines"),
        shift(4,customer="TUI",employee_id="007"),
        shift(5,customer="LATAM CARGO",day=date(2026,8,2)),
        shift(6,customer="ANDERELOCATIE"), shift(7,customer="DELTA AIRLINES EXTRA"),
        shift(8,customer="LUCHTHAVEN")))
    assert result.report.duplicate_rows == 1
    assert result.report.remaining_movements == 6


def test_location_mapping_configurable_and_conflicts_rejected():
    source = imported(shift(customer="DELTA AIRLINES"),shift(3,customer="TUI"))
    assert clean_import(source,policy=CleaningPolicy(location_aliases=())).report.remaining_movements == 2
    with pytest.raises(ValueError,match="Conflicting"):
        CleaningPolicy(location_aliases=(("TUI","A"),(" tui ","B")))
    with pytest.raises(ValueError):
        CleaningPolicy(location_aliases=(("TUI",""),))


@pytest.mark.skipif(not os.environ.get("PLANET_SOURCE"), reason="Opt-in private source")
def test_local_august_acceptance():
    source = import_planet(os.environ["PLANET_SOURCE"], month="2026-08")
    result = clean_import(source)
    r = result.report
    assert (r.input_rows, r.ghost_agent_rows, r.telework_rows, r.excluded_remark_rows,
            r.duplicate_rows, r.remaining_movements) == (1406, 105, 13, 0, 324, 964)
    assert all(s.day.month == 8 for m in result.movements for s in m.source_shifts)
    ghost_ids = set(result.policy.ghost_employee_ids)
    expected = {s.source_row for s in source.shifts if s.employee_id in ghost_ids}
    actual = {r.shift.source_row for r in result.removals if r.reason == "GHOST_AGENT"}
    assert actual == expected
    assert not any(s.employee_id in ghost_ids for m in result.movements for s in m.source_shifts)
    retained = [s for m in result.movements for s in m.source_shifts]
    expected_retained = [s for s in source.shifts if s.employee_id not in ghost_ids
                         and (s.remark or "").strip().casefold() != "telework"]
    assert sorted(s.source_row for s in retained) == sorted(s.source_row for s in expected_retained)
    airport_customers = {"DELTA AIRLINES", "HAINAN AIRLINES", "LATAM CARGO", "TUI", "ICTS BELGIUM BVBA"}
    seen = set()
    for movement in result.movements:
        if any(s.customer in airport_customers for s in movement.source_shifts):
            first = movement.source_shifts[0]
            assert (first.employee_id, first.day) not in seen
            seen.add((first.employee_id, first.day))
