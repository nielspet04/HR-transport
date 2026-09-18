"""Phase 4: process every source month and save selectable dashboard results."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.configuration.routes import RouteStore
from app.importers.planet import import_planet,ImportSourceError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--month',help='Compatibiliteitsoptie: controleer dat deze maand bestaat; verwerk steeds alle maanden')
    parser.add_argument('--db',type=Path,default=ROOT/'data/state/routes.sqlite3')
    args=parser.parse_args()
    try:
        if not args.db.exists():raise ValueError('Importeer eerst de nieuwe Sociaal-abo-basisgegevens.')
        store=RouteStore(args.db);config=store.snapshot()
        if args.month:
            imported=import_planet(args.source,month=args.month)
            if imported.has_errors:raise ValueError('Gevraagde maand ontbreekt of bron bevat fouten.')
        results=store.process_source(args.source,config['revision'])
    except (ValueError,OSError,ImportSourceError) as error:
        print(f'ERROR: {error}',file=sys.stderr);return 2
    for result in results:
        print(f"Maand: {result['month']} · Verwerking: {result['run_id']} · Resultaat: {result['summary']}")
    print('Opgeslagen voor dashboard met fase-5-controlebedragen voor gewone auto; geen definitieve uitbetaling. Fuzzy suggesties nooit automatisch bevestigd.')
    return 0


if __name__=='__main__':raise SystemExit(main())
