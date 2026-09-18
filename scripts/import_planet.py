"""Run phase-1 import and print an aggregate, privacy-conscious report only."""

import argparse
import sys
from collections import Counter
from pathlib import Path

# Also works before an editable install, when run from any current directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.importers.planet import ImportSourceError, import_planet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--month", help="Selecteer expliciet één maand: YYYY-MM")
    args = parser.parse_args()
    try:
        result = import_planet(args.source, month=args.month)
    except ImportSourceError as error:
        print(f"IMPORT ERROR: {error}", file=sys.stderr)
        return 2
    report = result.report
    for label, value in (
        ("Header op rij", report.header_row),
        ("Bronrijen onder header", report.data_rows_seen),
        ("Lege rijen", report.blank_rows),
        ("Samenvattingsregels", report.summary_rows),
        ("Herhaalde headers", report.repeated_header_rows),
        ("Afgewezen rijen", report.rejected_rows),
        ("Geïmporteerde shifts", report.imported_rows),
        ("Buiten gekozen maand", report.outside_month_rows),
        ("Maanden in geldige bronrijen", ", ".join(report.months)),
        ("Gekozen maand", report.selected_month or "alle maanden"),
    ):
        print(f"{label}: {value}")
    print("Meldingen voor de volledige bron, ook buiten de gekozen maand:")
    for (severity, code), count in sorted(Counter(
        (issue.severity, issue.code) for issue in result.issues
    ).items()):
        print(f"{severity} {code}: {count}")
    print("Geen persoonsgegevens of outputbestanden weggeschreven.")
    return 1 if result.has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
