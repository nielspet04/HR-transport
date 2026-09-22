"""Import external payroll references onto existing workers; dry-run by default."""
import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.configuration.external_references import import_external_references, read_external_references
from app.configuration.routes import RouteStore
from app.importers.reference import norm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--valid-from', required=True)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/state/routes.sqlite3')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.db.exists():
        parser.error('Bestaande werknemersdatabase ontbreekt.')
    if not args.apply:
        _, records = read_external_references(args.source)
        with sqlite3.connect(f'{args.db.resolve().as_uri()}?mode=ro', uri=True) as db:
            workers = {row[0] for row in db.execute('SELECT name_key FROM workers')}
            aliases = {norm(row[0]) for row in db.execute(
                "SELECT name FROM address_candidates WHERE status='LINKED' AND worker_id IS NOT NULL")}
        matched = sum(norm(record['name']) in workers | aliases for record in records)
        print(f'Loonreferenties: {len(records)} · bevestigde profielkoppelingen: {matched} · ter controle: {len(records)-matched} · geen wijzigingen')
        return
    directory = args.db.parent / 'backups'; directory.mkdir(parents=True, exist_ok=True); directory.chmod(0o700)
    backup = directory / f'voor-loonreferentieimport-{datetime.now().strftime("%Y%m%d-%H%M%S-%f")}.sqlite3'
    with sqlite3.connect(args.db) as original, sqlite3.connect(backup) as target:
        original.backup(target)
    backup.chmod(0o600)
    store = RouteStore(args.db)
    print(import_external_references(store, args.source, args.valid_from, store.snapshot()['revision']))
    print(f'Lokale databasebackup: {backup}')
    print('Geen werknemers aangemaakt. Bestaande adressen, routes en berekeningen ongewijzigd.')


if __name__ == '__main__':
    main()
