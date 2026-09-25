"""Simple reference-only routes; legacy HR configuration stays in another DB."""
from datetime import datetime, timezone
import json
import base64
import binascii
import tempfile
from zipfile import ZipFile,BadZipFile
from pathlib import Path

from .store import Store, required, valid_day, distance
from app.importers.reference import norm
from app.transport import km_applicable

# Explicit source labels, not fuzzy location recognition.
LOCATIONS={'apt':'LUCHTHAVEN','apt fiets':'LUCHTHAVEN','wework fiets':'WeWork'}

SCHEMA='''
CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL);
INSERT OR IGNORE INTO meta VALUES(1,0);
CREATE TABLE IF NOT EXISTS workers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS routes(id INTEGER PRIMARY KEY,worker_id INTEGER NOT NULL REFERENCES workers(id),location TEXT NOT NULL,location_key TEXT NOT NULL,mode TEXT NOT NULL,mode_key TEXT NOT NULL,source_rows TEXT NOT NULL DEFAULT '[]',UNIQUE(worker_id,location_key,mode_key));
CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY,route_id INTEGER NOT NULL REFERENCES routes(id),valid_from TEXT NOT NULL,kms TEXT,raw_distance TEXT,changed_at TEXT NOT NULL,reason TEXT NOT NULL,UNIQUE(route_id,valid_from));
CREATE TABLE IF NOT EXISTS route_imports(hash TEXT PRIMARY KEY,valid_from TEXT NOT NULL,report TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corrections(id INTEGER PRIMARY KEY,version_id INTEGER NOT NULL REFERENCES versions(id),previous TEXT NOT NULL,changed_at TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS matching_employee_links(planet_id TEXT PRIMARY KEY,worker_id INTEGER NOT NULL REFERENCES workers(id),source_keys TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS matching_location_links(customer TEXT PRIMARY KEY,location TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS matching_runs(id INTEGER PRIMARY KEY,month TEXT NOT NULL,created_at TEXT NOT NULL,source_path TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS excluded_months(month TEXT PRIMARY KEY,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS matching_audit(id INTEGER PRIMARY KEY,changed_at TEXT NOT NULL,reason TEXT NOT NULL,details TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS car_tariffs(id INTEGER PRIMARY KEY,valid_from TEXT NOT NULL,data TEXT NOT NULL,source TEXT NOT NULL,reason TEXT NOT NULL,changed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS special_car_tariffs(id INTEGER PRIMARY KEY,valid_from TEXT NOT NULL,data TEXT NOT NULL,source TEXT NOT NULL,reason TEXT NOT NULL,changed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS extra_shift_tariffs(id INTEGER PRIMARY KEY,valid_from TEXT NOT NULL,rate_per_km TEXT NOT NULL,source TEXT NOT NULL,reason TEXT NOT NULL,changed_at TEXT NOT NULL);
'''


class RouteStore(Store):
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            from .addresses import SCHEMA as ADDRESS_SCHEMA
            db.executescript(ADDRESS_SCHEMA)
            from .external_references import SCHEMA as EXTERNAL_REFERENCE_SCHEMA
            db.executescript(EXTERNAL_REFERENCE_SCHEMA)
            from app.geocoding import SCHEMA as GEOCODE_SCHEMA
            db.executescript(GEOCODE_SCHEMA)
            from .location_addresses import SCHEMA as LOCATION_ADDRESS_SCHEMA
            db.executescript(LOCATION_ADDRESS_SCHEMA)
            from app.routing import SCHEMA as ROUTING_SCHEMA
            db.executescript(ROUTING_SCHEMA)
            from app.route_corrections import SCHEMA as CORRECTIONS_SCHEMA
            db.executescript(CORRECTIONS_SCHEMA)
            from app.automatic_routes import SCHEMA as AUTOMATIC_SCHEMA
            db.executescript(AUTOMATIC_SCHEMA)
            from app.location_transfers import SCHEMA as TRANSFER_SCHEMA
            db.executescript(TRANSFER_SCHEMA)
            from app.shift_transport import SCHEMA as SHIFT_TRANSPORT_SCHEMA
            db.executescript(SHIFT_TRANSPORT_SCHEMA)
            from app.transport_defaults import SCHEMA as TRANSPORT_DEFAULT_SCHEMA
            db.executescript(TRANSPORT_DEFAULT_SCHEMA)
            from app.calculation_corrections import SCHEMA as CALCULATION_CORRECTION_SCHEMA
            db.executescript(CALCULATION_CORRECTION_SCHEMA)
            if not db.execute('SELECT 1 FROM bicycle_tariffs LIMIT 1').fetchone():
                db.execute('INSERT INTO bicycle_tariffs(valid_from,rate_per_km,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    ('2026-01-01','0.37','Projectbrief · fietsvergoeding €0,37/km',
                     'Initiële configureerbare fietsvergoeding uit projectbrief',datetime.now(timezone.utc).isoformat()))
            from app.calculation import pdf_start_tariff,pdf_special_tariff
            if not db.execute('SELECT 1 FROM extra_shift_tariffs LIMIT 1').fetchone():
                db.execute('INSERT INTO extra_shift_tariffs(valid_from,rate_per_km,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    ('2026-02-01','0.4326','Gebruiker bevestigt €0,4326/km · PDF vanaf 01/02/2026',
                     '48h starttarief; heen en terug bevestigd door gebruiker',datetime.now(timezone.utc).isoformat()))
            if not db.execute('SELECT 1 FROM special_car_tariffs LIMIT 1').fetchone():
                db.execute('INSERT INTO special_car_tariffs(valid_from,data,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    ('2026-02-01',json.dumps(pdf_special_tariff()),'accg-pc-317-vervoerskosten_9.pdf · vroeg/laat · 150%-kolom',
                     'Speciale kilometertabel bevestigd door gebruiker',datetime.now(timezone.utc).isoformat()))
            if not db.execute('SELECT 1 FROM car_tariffs LIMIT 1').fetchone():
                db.execute('INSERT INTO car_tariffs(valid_from,data,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    ('2026-02-01',json.dumps(pdf_start_tariff()),'accg-pc-317-vervoerskosten_9.pdf · gewone auto · 120%-kolom',
                     'Starttabel bevestigd door gebruiker',datetime.now(timezone.utc).isoformat()))
        self.path.chmod(0o600)

    @staticmethod
    def worker(db,name):
        name=required(name)
        db.execute('INSERT OR IGNORE INTO workers(name,name_key) VALUES(?,?)',(name,norm(name)))
        return db.execute('SELECT id FROM workers WHERE name_key=?',(norm(name),)).fetchone()[0]

    @staticmethod
    def version(db,route,start,kms,reason,raw=None,allow_missing=False,allow_historical=False):
        start=valid_day(start);reason=required(reason)
        if type(route) is not int or not db.execute('SELECT 1 FROM routes WHERE id=?',(route,)).fetchone():raise ValueError('Onbekende route.')
        if not km_applicable(db.execute('SELECT mode FROM routes WHERE id=?',(route,)).fetchone()[0]):kms=None;raw=None
        elif kms is None and not allow_missing:distance(kms)
        last=db.execute('SELECT max(valid_from) FROM versions WHERE route_id=?',(route,)).fetchone()[0]
        if last and start<last and not allow_historical:raise ValueError('Kies de laatste ingangsdatum of een latere datum; oudere versies blijven bewaard.')
        if allow_historical and db.execute('SELECT 1 FROM versions WHERE route_id=? AND valid_from=?',(route,start)).fetchone():raise ValueError('Op deze datum bestaat al een versie; kies een andere datum.')
        if last==start:
            previous=db.execute('SELECT * FROM versions WHERE route_id=? AND valid_from=?',(route,start)).fetchone()
            now=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO corrections(version_id,previous,changed_at,reason) VALUES(?,?,?,?)',(previous['id'],json.dumps(dict(previous)),now,reason))
            db.execute('UPDATE versions SET kms=?,raw_distance=?,changed_at=?,reason=? WHERE id=?',
                (distance(kms) if kms is not None else None,raw,now,reason,previous['id']))
            return
        db.execute('INSERT INTO versions(route_id,valid_from,kms,raw_distance,changed_at,reason) VALUES(?,?,?,?,?,?)',
            (route,start,distance(kms) if kms is not None else None,raw,datetime.now(timezone.utc).isoformat(),reason))

    def import_source(self,result,start):
        start=valid_day(start)
        if result.has_errors:raise ValueError('Bron bevat importfouten.')
        groups={}
        for record in result.records:
            if not record.employee_name or not record.location or not record.transport_mode:
                raise ValueError(f'Bronrij {record.source_row}: naam, locatie en vervoer zijn verplicht.')
            loc=LOCATIONS.get(norm(record.location),record.location.strip())
            key=(norm(record.employee_name),norm(loc),norm(record.transport_mode))
            groups.setdefault(key,[]).append((record,loc))
        report={'source_rows':len(result.records),'routes':len(groups),'duplicates':len(result.records)-len(groups),'review':0}
        with self.transaction() as db:
            digest=result.report.source_sha256
            old=db.execute('SELECT report,valid_from FROM route_imports WHERE hash=?',(digest,)).fetchone()
            if old:
                if old['valid_from']!=start:raise ValueError('Deze bron is al ingelezen met een andere startdatum.')
                return {**json.loads(old['report']),'already_imported':True}
            # New imports may add routes, but never silently replace edited ones.
            for members in groups.values():
                record,loc=members[0]
                employee=self.worker(db,record.employee_name)
                values={r.distance for r,_ in members}
                kms=record.distance if len(values)==1 and record.distance is not None else None
                raw=str(dict(record.source_values)['Afstand']) if kms is None else None
                if len(values)>1:raw=' / '.join(str(dict(r.source_values)['Afstand']) for r,_ in members)
                if kms is None and km_applicable(record.transport_mode):report['review']+=1
                existing=db.execute('SELECT id FROM routes WHERE worker_id=? AND location_key=? AND mode_key=?',
                    (employee,norm(loc),norm(record.transport_mode))).fetchone()
                if existing:raise ValueError('Route bestaat al: import gestopt om handmatige wijzigingen te beschermen.')
                route=db.execute('INSERT INTO routes(worker_id,location,location_key,mode,mode_key,source_rows) VALUES(?,?,?,?,?,?)',
                    (employee,loc,norm(loc),required(record.transport_mode),norm(record.transport_mode),json.dumps([r.source_row for r,_ in members]))).lastrowid
                self.version(db,route,start,kms,'Nieuwe Sociaal-abo-bron',raw,allow_missing=True)
            report['workers']=db.execute('SELECT count(*) FROM workers').fetchone()[0]
            db.execute('INSERT INTO route_imports VALUES(?,?,?)',(digest,start,json.dumps(report)))
        return report

    def apply(self,action,data,revision):
        if action in ('automatic_settings','automatic_process'):
            if type(revision) is not int:raise ValueError('Vernieuw het dashboard.')
            with self.transaction(revision) as db:
                if action=='automatic_settings':
                    if type(data.get('enabled')) is not bool:raise ValueError('Kies automatisch aan of uit.')
                    if data['enabled'] and data.get('consent') is not True:raise ValueError('Bevestig automatische Mapbox-aanvragen en opslag.')
                    db.execute('UPDATE automatic_route_settings SET enabled=? WHERE id=1',(int(data['enabled']),))
                    db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),'Gebruiker kiest automatische Mapbox-verwerking',json.dumps({'action':action,'enabled':data['enabled']})))
            from app.automatic_routes import trigger
            trigger(self);return
        result=self._apply(action,data,revision)
        if action in ('planet_upload','matching_refresh','matching_employee','matching_location','employee_onboard','customer_onboard','address_save','address_link','location_address_save','route_add','route_historical','worker_rename','geocode_review','geocode_review_many','shift_transport_choice','transport_default'):
            from app.automatic_routes import trigger
            trigger(self)
        return result

    def _apply(self,action,data,revision):
        if type(revision) is not int:raise ValueError('Vernieuw eerst het scherm.')
        if action=='employee_onboard':
            from app.employee_onboarding import onboard
            return onboard(self,data,revision)
        if action=='customer_onboard':
            from app.customer_onboarding import onboard
            return onboard(self,data,revision)
        if action=='location_transfer_override':
            from app.location_transfers import correct
            return correct(self,data,revision)
        if action=='shift_transport_choice':
            from app.shift_transport import save
            return save(self,data,revision)
        if action=='transport_default':
            from app.transport_defaults import save
            return save(self,data,revision)
        if action=='calculation_amount_correction':
            from app.calculation_corrections import save
            return save(self,data,revision)
        if action=='route_distance_override':
            from app.route_corrections import apply
            return apply(self,data,revision)
        if action=='route_visualization_request':
            from app.routing import request_visualization
            return request_visualization(self,data,revision)
        if action=='route_distance_request':
            from app.routing import request_one
            return request_one(self,data,revision)
        if action=='location_geocode':
            from .location_addresses import geocode
            return geocode(self,data,revision)
        if action=='geocode_review_many':
            from app.geocoding import review_many
            return review_many(self,data,revision)
        if action in ('address_geocode','address_geocode_bulk_item','geocode_review'):
            from app.geocoding import apply
            return apply(self,action,data,revision)
        if action=='planet_upload':return self.upload_planet(data,revision)
        if action in ('matching_employee','matching_location','matching_refresh'):
            return self.apply_matching(action,data,revision)
        with self.transaction(revision) as db:
            if action=='location_address_save':
                from .location_addresses import save
                return save(db,data)
            elif action in ('address_save','address_link','address_ignore'):
                from .addresses import apply
                return apply(db,action,data)
            elif action in ('external_reference_save','external_reference_link','external_reference_ignore'):
                from .external_references import apply
                return apply(db,action,data)
            elif action=='extra_shift_tariff':
                from app.calculation import validate_km_rate
                start=valid_day(data.get('valid_from'));reason=required(data.get('reason'));rate=validate_km_rate(data.get('rate_per_km'))
                db.execute('INSERT INTO extra_shift_tariffs(valid_from,rate_per_km,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    (start,rate,'HR-configuratie',reason,datetime.now(timezone.utc).isoformat()))
            elif action=='bicycle_tariff':
                from app.calculation import validate_km_rate
                start=valid_day(data.get('valid_from'));reason=required(data.get('reason'));rate=validate_km_rate(data.get('rate_per_km'))
                db.execute('INSERT INTO bicycle_tariffs(valid_from,rate_per_km,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    (start,rate,'HR-configuratie',reason,datetime.now(timezone.utc).isoformat()))
            elif action in ('car_tariff','special_car_tariff'):
                from app.calculation import validate_tariff
                start=valid_day(data.get('valid_from'));reason=required(data.get('reason'))
                table='special_car_tariffs' if action=='special_car_tariff' else 'car_tariffs'
                tariff=validate_tariff(data)
                db.execute(f'INSERT INTO {table}(valid_from,data,source,reason,changed_at) VALUES(?,?,?,?,?)',
                    (start,json.dumps(tariff),'HR-configuratie',reason,datetime.now(timezone.utc).isoformat()))
            elif action=='worker_rename':
                name=required(data.get('name'))
                if not db.execute('SELECT 1 FROM workers WHERE id=?',(data.get('worker_id'),)).fetchone():raise ValueError('Onbekende werknemer.')
                db.execute('UPDATE workers SET name=?,name_key=? WHERE id=?',(name,norm(name),data['worker_id']))
            elif action=='route_add':
                employee=self.worker(db,data.get('name'))
                loc=required(data.get('location'));loc=LOCATIONS.get(norm(loc),loc)
                mode=required(data.get('mode'))
                if db.execute('SELECT 1 FROM routes WHERE worker_id=? AND location_key=? AND mode_key=?',(employee,norm(loc),norm(mode))).fetchone():
                    raise ValueError('Deze werknemer/locatie/vervoer-route bestaat al. Gebruik Aanpassen.')
                route=db.execute('INSERT INTO routes(worker_id,location,location_key,mode,mode_key) VALUES(?,?,?,?,?)',
                    (employee,loc,norm(loc),mode,norm(mode))).lastrowid
                self.version(db,route,data.get('valid_from'),data.get('kms'),data.get('reason'))
            elif action=='route_update':
                self.version(db,data.get('route_id'),data.get('valid_from'),data.get('kms'),data.get('reason'))
            elif action=='route_historical':
                if data.get('confirm') is not True:raise ValueError('Bevestig de vervoerswijze voor deze eerdere periode.')
                route=db.execute('SELECT * FROM routes WHERE id=?',(data.get('route_id'),)).fetchone()
                if not route:raise ValueError('Onbekende route.')
                self.version(db,route['id'],data.get('valid_from'),None,data.get('reason'),allow_missing=True,allow_historical=True)
                db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',
                    (datetime.now(timezone.utc).isoformat(),required(data.get('reason')),json.dumps({'action':action,'route_id':route['id'],'valid_from':data.get('valid_from')})))
            elif action=='worker_move':
                updates=data.get('updates')
                if not isinstance(updates,list) or not updates or any(not isinstance(u,dict) for u in updates):raise ValueError('Vul alle routes in.')
                actual=[u.get('route_id') for u in updates]
                expected={r[0] for r in db.execute('SELECT id FROM routes WHERE worker_id=?',(data.get('worker_id'),))}
                if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Vul precies alle routes van de werknemer in.')
                for u in updates:self.version(db,u['route_id'],data.get('valid_from'),u.get('kms'),data.get('reason'))
            else:raise ValueError('Onbekende actie. Herstart het dashboard na een codewijziging.')

    def snapshot(self):
        with self.connect() as db:
            config=self.matching_config(db)
            matching_config=config
            from app.distances import display_route
            from app.route_corrections import cached_distances
            from app.automatic_routes import state as automatic_state
            config={**config,'versions':[display_route(v) for v in config['versions']]}
            from app.shift_transport import snapshot as shift_transport_snapshot
            from .addresses import snapshot as address_snapshot
            from app.geocoding import enrich, configured, bulk_plan
            addresses=address_snapshot(db)
            enrich(db,addresses['addresses'])
            from .external_references import snapshot as external_reference_snapshot
            from .location_addresses import snapshot as location_snapshot
            latest=db.execute('SELECT id,payload FROM matching_runs WHERE month NOT IN (SELECT month FROM excluded_months) ORDER BY id DESC LIMIT 1').fetchone()
            issues=[];issue_warning=None
            if latest:
                from app.routing import plan
                try:issues=plan(db,matching_config,latest['id'])['blocked']
                except ValueError as error:issue_warning=str(error)
            from app.location_transfers import overview as transfer_overview
            from app.route_preview import catalog as route_map_catalog
            return {'view':'routes','app_version':'phase10-shift-telework-v1','revision':db.execute('SELECT revision FROM meta').fetchone()[0],**config,**shift_transport_snapshot(db),**addresses,**external_reference_snapshot(db),**location_snapshot(db),'mapbox_configured':configured(),'geocoding_bulk_plan':bulk_plan(addresses['addresses']),'automatic_routes':automatic_state(db),
                'route_distances':cached_distances(db),
                'route_maps':route_map_catalog(db),
                'route_issues':issues,'route_issue_warning':issue_warning,
                'location_transfers':transfer_overview(db,matching_config),
                'matching_runs':[{'id':r['id'],'month':r['month'],'created_at':r['created_at'],'source_sha256':json.loads(r['payload']).get('source_sha256')} for r in db.execute('SELECT id,month,created_at,payload FROM matching_runs WHERE month NOT IN (SELECT month FROM excluded_months) ORDER BY id DESC')],
                'matching':self.matching_payload(latest,matching_config,db) if latest else None}

    @staticmethod
    def matching_config(db):
        config={**{table:[dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY id')] for table in ('workers','routes','versions')},
            'car_tariffs':[{**dict(r),'data':json.loads(r['data'])} for r in db.execute('SELECT * FROM car_tariffs ORDER BY id')],
            'special_car_tariffs':[{**dict(r),'data':json.loads(r['data'])} for r in db.execute('SELECT * FROM special_car_tariffs ORDER BY id')],
            'extra_shift_tariffs':[dict(r) for r in db.execute('SELECT * FROM extra_shift_tariffs ORDER BY id')],
            'bicycle_tariffs':[dict(r) for r in db.execute('SELECT * FROM bicycle_tariffs ORDER BY id')],
            'transport_defaults':[dict(r) for r in db.execute('SELECT * FROM transport_defaults ORDER BY id')],
            'employee_links':[dict(r) for r in db.execute('SELECT * FROM matching_employee_links ORDER BY planet_id')],
            'location_links':[dict(r) for r in db.execute('SELECT * FROM matching_location_links ORDER BY customer')]}
        excluded={r['id'] for r in config['routes'] if not km_applicable(r['mode'])}
        for route in config['routes']:route['km_applicable']=route['id'] not in excluded
        for version in config['versions']:
            if version['route_id'] in excluded:version['kms']=None;version['raw_distance']=None
        return config

    def get_route_plan(self,run_id):
        if type(run_id) is not int:raise ValueError('Selecteer een exportverwerking.')
        from app.routing import plan
        with self.connect() as db:return plan(db,self.matching_config(db),run_id)

    @staticmethod
    def matching_payload(row,config,db=None):
        from app.matching import configuration_digest
        from app.distances import display_route
        from app.calculation import calculate_month
        payload=json.loads(row['payload'])
        for movement in payload['movements']:
            movement['routes']=[display_route(r) for r in movement.get('routes',[])]
        if 'calculation' in payload and payload['configuration_digest']==configuration_digest(config):
            payload['calculation']=calculate_month(payload['movements'],config.get('car_tariffs',[]))
        if db is not None and 'calculation' in payload:
            from app.shift_transport import choices as transport_choices
            choice_map=transport_choices(db,payload)
            for movement in payload['movements']:
                movement['transport_choice']=choice_map.get(movement['id'])
            from app.cached_calculation import calculate_cached_month
            payload['calculation']=calculate_cached_month(db,config,row['id'],payload)
            payload['movements']=payload['calculation'].pop('resolved_movements')
        if db is not None:
            from app.coverage import check
            payload['coverage']=check(db,payload)
            from app.routing import plan
            try:payload['route_issues']=[issue for issue in plan(db,config,row['id'])['blocked'] if issue['day'].startswith(payload['month'])]
            except ValueError as error:payload['route_issue_warning']=str(error)
        return {**payload,'run_id':row['id'],'stale':payload['configuration_digest']!=configuration_digest(config)}

    def get_matching(self,run_id):
        with self.connect() as db:
            row=db.execute('SELECT id,payload FROM matching_runs WHERE id=? AND month NOT IN (SELECT month FROM excluded_months)',(run_id,)).fetchone()
            if not row:raise ValueError('Onbekende maandverwerking.')
            return self.matching_payload(row,self.matching_config(db),db)

    @staticmethod
    def insert_matching(db,payload,source):
        return db.execute('INSERT INTO matching_runs(month,created_at,source_path,payload) VALUES(?,?,?,?)',
            (payload['month'],payload['created_at'],str(Path(source).resolve()),json.dumps(payload,ensure_ascii=False))).lastrowid

    def save_matching(self,payload,source,revision):
        with self.transaction(revision) as db:return self.insert_matching(db,payload,source)

    def process_source(self,source,revision):
        """Publish all source months together, or none on any failure."""
        with self.transaction(revision) as db:
            return self.process_matching_file(db,source)

    def upload_planet(self,data,revision):
        """Keep a private source copy so refresh never depends on Downloads."""
        name=required(data.get('filename'))
        encoded=data.get('content')
        if not name.lower().endswith('.xlsx') or not isinstance(encoded,str) or len(encoded)>7_000_000:
            raise ValueError('Kies een .xlsx-bestand van maximaal 5 MB.')
        try:content=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error):raise ValueError('Ongeldige bestandsinhoud.') from None
        if not content or len(content)>5_000_000:raise ValueError('Bestand leeg of groter dan 5 MB.')
        directory=self.path.parent/'planet_uploads';directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
        with tempfile.NamedTemporaryFile(dir=directory,prefix='planet-',suffix='.xlsx',delete=False) as file:
            file.write(content);source=Path(file.name)
        try:
            with ZipFile(source) as archive:
                entries=archive.infolist()
                if len(entries)>2000 or sum(e.file_size for e in entries)>64_000_000:
                    raise ValueError('Excelbestand bevat te veel uitgepakte gegevens.')
            return self.process_source(source,revision)
        except BadZipFile:
            source.unlink();raise ValueError('Geen geldig Excelbestand.') from None
        except Exception:
            source.unlink();raise

    def process_matching_file(self,db,source,expected_hash=None):
        from dataclasses import replace
        from app.importers.planet import import_planet
        from app.matching import match_import
        try:imported=import_planet(source)
        except Exception:raise ValueError('Bronbestand niet leesbaar. Herstel het bronbestand en probeer opnieuw.') from None
        if expected_hash and imported.report.source_sha256!=expected_hash:
            raise ValueError('Bronbestand gewijzigd. Importeer het volledige bestand opnieuw vóór bevestiging.')
        if imported.has_errors:raise ValueError('Los de Pl@net-importfouten eerst op; geen maanden opgeslagen.')
        if not imported.report.months:raise ValueError('Geen shiften gevonden in het bronbestand.')
        config=self.matching_config(db);results=[]
        excluded={r['month'] for r in db.execute('SELECT month FROM excluded_months')}
        selected_imports=[]
        for month in imported.report.months:
            if month in excluded:continue
            shifts=tuple(s for s in imported.shifts if s.day.strftime('%Y-%m')==month)
            selected=replace(imported,shifts=shifts,report=replace(imported.report,
                selected_month=month,imported_rows=len(shifts),outside_month_rows=len(imported.shifts)-len(shifts)))
            selected_imports.append(selected)
        location_config=Path(__file__).resolve().parents[3]/'config/locations.toml'
        from app.default_transport import seed
        seed(self,db,[match_import(selected,config,location_config) for selected in selected_imports])
        config=self.matching_config(db)
        for selected in selected_imports:
            month=selected.report.selected_month
            payload=match_import(selected,config,Path(__file__).resolve().parents[3]/'config/locations.toml')
            results.append({'month':month,'run_id':self.insert_matching(db,payload,source),'summary':payload['summary']})
        return results

    def apply_matching(self,action,data,revision):
        from app.matching import key
        with self.transaction(revision) as db:
            run=db.execute('SELECT * FROM matching_runs WHERE id=?',(data.get('run_id'),)).fetchone()
            if not run:raise ValueError('Importeer eerst een maand met scripts/match_planet.py.')
            previous=json.loads(run['payload'])
            if action=='matching_refresh':
                self.process_matching_file(db,run['source_path'])
                return
            reason=required(data.get('reason'))
            if action=='matching_employee':
                agent=next((a for a in previous['agents'] if a['planet_id']==data.get('planet_id')),None)
                worker=data.get('worker_id')
                if not agent or type(worker) is not int or not db.execute('SELECT 1 FROM workers WHERE id=?',(worker,)).fetchone():raise ValueError('Kies een bestaande agent en werknemer.')
                db.execute('INSERT INTO matching_employee_links VALUES(?,?,?) ON CONFLICT(planet_id) DO UPDATE SET worker_id=excluded.worker_id,source_keys=excluded.source_keys',
                    (agent['planet_id'],worker,json.dumps(agent['source_keys'])))
            else:
                customer=data.get('customer');location=required(data.get('location'))
                if not any(r['customer']==customer for r in previous['locations']):raise ValueError('Onbekende bronklant.')
                if not db.execute('SELECT 1 FROM routes WHERE location_key=?',(norm(location),)).fetchone():raise ValueError('Kies een bestaande fysieke locatie.')
                db.execute('INSERT INTO matching_location_links VALUES(?,?) ON CONFLICT(customer) DO UPDATE SET location=excluded.location',(key(customer),location))
            db.execute('INSERT INTO matching_audit(changed_at,reason,details) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),reason,json.dumps({'action':action,**data})))
            self.process_matching_file(db,run['source_path'],previous['source_sha256'])

    def resolve(self,route,day):
        with self.connect() as db:
            row=db.execute('SELECT * FROM versions WHERE route_id=? AND valid_from<=? ORDER BY valid_from DESC LIMIT 1',(route,valid_day(day))).fetchone()
            result=dict(row) if row else None
            mode=db.execute('SELECT mode FROM routes WHERE id=?',(route,)).fetchone()
            if result and mode and not km_applicable(mode[0]):result['kms']=None;result['raw_distance']=None
            return result
