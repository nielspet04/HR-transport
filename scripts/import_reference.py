"""Phase-3 reference import: metadata and aggregate quality report only."""
import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from app.importers.reference import import_reference
from app.importers.planet import ImportSourceError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--show-issues',action='store_true',help='Toon bronrij en veld bij elke melding, geen bronwaarden')
    args = parser.parse_args()
    try:
        result = import_reference(args.source)
    except ImportSourceError as error:
        print(f'IMPORT ERROR: {error}',file=sys.stderr)
        return 2
    for key in ('header_row','data_rows_seen','blank_rows','repeated_header_rows',
                'ignored_nondata_rows','ignored_special_rows','imported_rows','unresolved_rows'):
        print(f'{key}: {getattr(result.report,key)}')
    for (severity,code),count in sorted(Counter((i.severity,i.code) for i in result.issues).items()):
        print(f'{severity} {code}: {count}')
    if args.show_issues:
        for issue in result.issues:
            print(f'{issue.severity} {issue.code}: rij {issue.source_row}, veld {issue.field or "—"}')
    print('Geen HR-records opgeslagen, geen koppeling met shiften, geen berekeningen.')
    return 1 if result.has_errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
