"""Generate a private, read-only route control workbook without Mapbox calls."""
import argparse
from datetime import datetime
import os
from pathlib import Path
from app.configuration.routes import RouteStore
from app.distance_export import workbook_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',default='data/state/routes.sqlite3')
    parser.add_argument('--run-id',type=int)
    parser.add_argument('--output',default='outputs/routecontrole/werknemersafstanden-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.xlsx')
    args=parser.parse_args()
    database=Path(args.database)
    if not database.is_file():parser.error('Database niet gevonden.')
    store=RouteStore(database)
    with store.connect() as db:
        latest=db.execute('SELECT id FROM matching_runs ORDER BY id DESC LIMIT 1').fetchone()
    if not latest:parser.error('Geen opgeslagen exportverwerking.')
    content=workbook_bytes(store,args.run_id or latest['id'])
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as file:file.write(content)
    print(output.resolve())


if __name__=='__main__':main()
