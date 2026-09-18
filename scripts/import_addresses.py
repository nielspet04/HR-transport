"""Import addresses onto existing workers; dry-run by default."""
import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.configuration.addresses import import_addresses, read_addresses
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
        from collections import Counter
        _, records = read_addresses(args.source)
        with sqlite3.connect(f'{args.db.resolve().as_uri()}?mode=ro', uri=True) as db:
            keys = {r[0] for r in db.execute('SELECT name_key FROM workers')}
        counts = Counter(norm(r['name']) for r in records)
        exact = sum(norm(r['name']) in keys and counts[norm(r['name'])] == 1 for r in records)
        print(f"Adresrijen: {len(records)} · unieke exacte naamkoppelingen: {exact} · overige: {len(records)-exact} · geen wijzigingen")
        return
    # Consistent backup before additive schema migration or import.
    directory = args.db.parent / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    backup = directory / f'voor-adresimport-{datetime.now().strftime("%Y%m%d-%H%M%S-%f")}.sqlite3'
    with sqlite3.connect(args.db) as original, sqlite3.connect(backup) as target:
        original.backup(target)
    backup.chmod(0o600)
    store = RouteStore(args.db)
    print(import_addresses(store, args.source, args.valid_from, store.snapshot()['revision']))
    print(f'Lokale databasebackup: {backup}')
    print('Geen werknemers aangemaakt. Geen Mapbox-verzoeken. Kilometerberekeningen ongewijzigd.')


if __name__ == '__main__':
    main()
