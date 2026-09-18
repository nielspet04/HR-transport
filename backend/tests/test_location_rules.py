"""Source kilometers never establish locations; only explicit mappings do."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.cleaning import CleaningPolicy, clean_import
from app.cleaning.locations import LocationRule, load_location_rules
from test_planet_cleaning import shift, imported


@pytest.mark.parametrize("kms", [Decimal("10"), Decimal("999"), Decimal("0"), Decimal("-1"), None])
def test_unconfirmed_customer_never_merged_from_distance(kms):
    result = clean_import(imported(shift(customer="TUI",kms=kms),
                                  shift(3,customer="UNKNOWN",kms=kms)))
    assert result.report.remaining_movements == 2
    assert result.report.duplicate_rows == 0


def test_icts_airport_confirmed_despite_different_distances():
    result = clean_import(imported(shift(customer="TUI",kms=Decimal("10")),
        shift(3,customer="ICTS BELGIUM BVBA",kms=Decimal("999"))))
    assert result.report.remaining_movements == 1
    assert result.report.duplicate_rows == 1
    assert len(result.movements[0].source_shifts) == 2


def test_confirmation_reused_and_valid_only_from_confirmed_date():
    policy = CleaningPolicy(location_aliases=(),location_rules=(LocationRule("TUI","AIRPORT"),
        LocationRule("NEW","AIRPORT",date(2026,9,1))),location_config_version="v2")
    assert clean_import(imported(shift(customer="TUI"),shift(3,customer="NEW")),policy=policy).report.remaining_movements == 2
    source = imported(shift(customer="TUI",day=date(2026,9,1)),
                      shift(3,customer="NEW",day=date(2026,9,1)),month="2026-09")
    assert clean_import(source,policy=policy).report.remaining_movements == 1
    assert clean_import(source,policy=policy).report.remaining_movements == 1


def test_historical_rules_dates_inclusive_and_overlap_rejected():
    rules = (LocationRule("A","OLD",date(2026,1,1),date(2026,7,31)),
             LocationRule("A","NEW",date(2026,8,1)))
    policy = CleaningPolicy(location_aliases=(),location_rules=rules)
    assert policy.location_for("A",date(2026,7,31)) == "OLD"
    assert policy.location_for("A",date(2026,8,1)) == "NEW"
    assert policy.location_for("A",date(2025,12,31)) is None
    with pytest.raises(ValueError,match="Overlapping"):
        CleaningPolicy(location_aliases=(),location_rules=(rules[0],LocationRule("A","NEW",date(2026,7,31))))


def test_config_saved_loaded_and_validation(tmp_path):
    path = tmp_path / "locations.toml"
    path.write_text('version = "v2"\n[[locations]]\ncustomer = "NEW"\nlocation = "AIRPORT"\nvalid_from = 2026-08-01\n')
    version,rules = load_location_rules(path)
    assert version == "v2" and rules[0].valid_from == date(2026,8,1)
    assert load_location_rules(path) == (version,rules)
    path.write_text('version = "v2"\n[[locations]]\ncustomer = "NEW"\nlocation = "AIRPORT"\nvalid_from = "2026-08-01"\n')
    with pytest.raises(ValueError):
        load_location_rules(path)
    with pytest.raises(ValueError):
        load_location_rules(tmp_path / "missing.toml")


def test_default_config_and_service_have_same_confirmed_locations():
    _,rules = load_location_rules(Path(__file__).resolve().parents[2] / "config/locations.toml")
    configured = CleaningPolicy(location_aliases=(),location_rules=rules)
    for customer in ("DELTA AIRLINES","HAINAN AIRLINES","LATAM CARGO","TUI","ICTS BELGIUM BVBA"):
        assert configured.location_for(customer,date(2026,8,1)) == "LUCHTHAVEN"
        assert CleaningPolicy().location_for(customer,date(2026,8,1)) == "LUCHTHAVEN"
