"""Phase-2 aggregate report: explicit month or explicit full-file processing."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cleaning import CleaningPolicy, clean_import
from app.cleaning.locations import load_location_rules
from app.importers.planet import ImportSourceError, import_planet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--month", help="YYYY-MM, bijvoorbeeld 2026-08")
    scope.add_argument("--all-months", action="store_true")
    parser.add_argument("--exclude-remark", action="append", default=[],
                        help="Extra door HR bevestigde uitsluiting; herhaalbaar")
    parser.add_argument("--location-config", type=Path,
                        default=Path(__file__).resolve().parents[1] / "config/locations.toml")
    parser.add_argument("--settings-db", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/state/transport.sqlite3")
    args = parser.parse_args()
    try:
        imported = import_planet(args.source, month=args.month)
        print(f"Bronrijen onder header (volledige bron): {imported.report.data_rows_seen}")
        print(f"Summary verwijderd (volledige bron, niet aan maand toegewezen): {imported.report.summary_rows}")
        print(f"Buiten gekozen maand: {imported.report.outside_month_rows}")
        if imported.has_errors:
            print("Cleaning gestopt: importfouten in de bron; controleer scripts/import_planet.py.",
                  file=sys.stderr)
            return 1
        version, rules = load_location_rules(args.location_config)
        policy=CleaningPolicy(
            tuple(args.exclude_remark), location_aliases=(), location_rules=rules,
            location_config_version=version)
        if args.settings_db.exists():
            from app.configuration.store import Store
            policy=Store(args.settings_db).cleaning_policy(policy)
        result = clean_import(imported, policy=policy)
    except (ImportSourceError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    report = result.report
    print(f"Cleaningperiode: {report.selected_month or 'alle maanden (expliciet gekozen)'}")
    for label, value in (
        ("Ingelezen voor cleaning", report.input_rows),
        ("Verwijderd als ghost-agent", report.ghost_agent_rows),
        ("Verwijderd als telework", report.telework_rows),
        ("Verwijderd als bevestigde niet-relevante categorie", report.excluded_remark_rows),
        ("Verwijderd als duplicate beweging", report.duplicate_rows),
        ("Overgebleven bewegingen", report.remaining_movements),
        ("Behouden rijen met unresolved Remark", report.unresolved_remark_rows),
    ):
        print(f"{label}: {value}")
    print(f"Locatieconfiguratieversie: {result.policy.location_config_version}")
    print("Locaties uitsluitend handmatig bevestigd; bron-Kms worden niet gebruikt voor groepering.")
    print("Dubbele bronshiften blijven als bewijs in hun beweging bewaard.")
    print("Bronvalidatie betreft het volledige bestand; cleaning alleen de gekozen periode.")
    print("Geen outputbestanden weggeschreven. Geen tarieven berekend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
