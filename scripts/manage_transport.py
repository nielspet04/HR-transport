"""Start local persistent transport configuration; Excel is optional bootstrap."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.configuration.store import Store
from app.configuration.routes import RouteStore
from app.configuration.server import make_server
from app.importers.reference import import_reference
from app.importers.planet import import_planet, ImportSourceError
from app.cleaning import clean_import, CleaningPolicy
from app.cleaning.locations import load_location_rules


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,help='Andere lokale database; standaard routes.sqlite3')
    parser.add_argument('--legacy',action='store_true',help='Open uitsluitend het oude beheer met zijn eigen database')
    parser.add_argument('--sheet',default='Niels',help='Bronblad van de nieuwe referentie (standaard Niels)')
    parser.add_argument('--reference',type=Path,help='Eenmalige vertrouwde Excel-startbron')
    parser.add_argument('--confirm-reference-from',help='Bevestig beschikbare startregels automatisch vanaf YYYY-MM-DD (ook eerder ingelezen regels)')
    parser.add_argument('--planet',type=Path,help='Pl@net-export met nieuwe/te koppelen agenten')
    parser.add_argument('--month',help='Verplichte YYYY-MM-selectie bij --planet')
    parser.add_argument('--seed-only',action='store_true')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--backup',type=Path,help='Nieuwe databasebackup; bestaand bestand wordt geweigerd')
    args=parser.parse_args()
    if args.planet and not args.month:parser.error('--planet vereist --month')
    if args.month and not args.planet:parser.error('--month vereist --planet')
    if args.reference and not args.confirm_reference_from:parser.error('--reference vereist --confirm-reference-from YYYY-MM-DD voor de basisinstellingen')
    if args.planet and not args.legacy:parser.error('Nieuwe fase 3 gebruikt alleen Sociaal abo; Planet blijft in fase 1/2.')
    try:
        # Validate all requested inputs before creating/updating the database.
        reference=import_reference(args.reference,**({} if args.legacy else {'sheet_name':args.sheet,'route_aware':True})) if args.reference else None
        if not args.legacy:
            store=RouteStore(args.db or ROOT/'data/state/routes.sqlite3')
            if reference:print(f'Nieuwe routes ingelezen: {store.import_source(reference,args.confirm_reference_from)}')
            elif args.confirm_reference_from:raise ValueError('Geef de nieuwe referentie-Excel mee.')
            if args.backup:store.backup(args.backup);print('Lokale databasebackup opgeslagen.')
            if args.seed_only:return 0
            server=make_server(store,args.port)
        else:
            return legacy_main(args,reference)
    except (ValueError,ImportSourceError,OSError) as error:
        print(f'ERROR: {error}',file=sys.stderr); return 2
    return serve(server)


def legacy_main(args,reference):
    try:
        version,rules=load_location_rules(ROOT/'config/locations.toml')
        policy=CleaningPolicy(location_aliases=(),location_rules=rules,location_config_version=version)
        imported_planet=import_planet(args.planet,month=args.month) if args.planet else None
        if imported_planet and imported_planet.has_errors:raise ValueError('Pl@net-import bevat fouten; beheerimport gestopt.')
        store=Store(args.db or ROOT/'data/state/transport.sqlite3')
        store.bootstrap_locations(rules)
        if reference:print(f'Startregels toegevoegd: {store.seed_reference(reference)}')
        if args.confirm_reference_from:
            print(f'Automatische bevestiging: {store.confirm_reference(args.confirm_reference_from)}')
        if imported_planet:
            planet=clean_import(imported_planet,policy=store.cleaning_policy(policy))
            print(f'Pl@net-agenten geregistreerd (geen automatische naammatching): {store.register_planet(planet)}')
        if args.backup:store.backup(args.backup); print('Lokale databasebackup opgeslagen.')
        if args.seed_only:return 0
        server=make_server(store,args.port)
    except (ValueError,ImportSourceError,OSError) as error:
        print(f'ERROR: {error}',file=sys.stderr); return 2
    return serve(server)


def serve(server):
    print(f'Beheer: http://127.0.0.1:{server.server_port}')
    print('Alleen lokaal, één gebruiker. Niet publiek hosten. Stop met Ctrl+C.')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
