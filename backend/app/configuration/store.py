"""Local SQLite settings. Immutable effective-date versions; atomic relocation."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3

from app.importers.reference import norm

MODES=('PRIVATE_CAR','BIKE','TRAIN','COMPANY_CAR')


def required(value):
    if not isinstance(value,str) or not value.strip() or len(value)>250:
        raise ValueError('Vul geldige tekst in (maximaal 250 tekens).')
    return value.strip()


def valid_day(value):
    if not isinstance(value,str):raise ValueError('Ingangsdatum vereist: YYYY-MM-DD.')
    try:
        parsed=date.fromisoformat(value)
        if parsed.isoformat()!=value:raise ValueError
        return value
    except ValueError:
        raise ValueError('Ingangsdatum vereist: YYYY-MM-DD.') from None


def distance(value):
    try:
        if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):raise InvalidOperation
        parsed=Decimal(str(value).replace(',','.'))
        if not parsed.is_finite() or parsed<0:raise InvalidOperation
        return str(parsed)
    except (InvalidOperation,ValueError):
        raise ValueError('Kilometers moeten een eindig, niet-negatief getal zijn.') from None


SCHEMA='''
CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL);
INSERT OR IGNORE INTO meta VALUES(1,0);
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS aliases(source TEXT NOT NULL, name_key TEXT NOT NULL, location_id INTEGER NOT NULL REFERENCES locations(id), PRIMARY KEY(source,name_key));
CREATE TABLE IF NOT EXISTS planet_agents(planet_id TEXT PRIMARY KEY, name TEXT NOT NULL, employee_id INTEGER REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS imports(hash TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY, import_hash TEXT NOT NULL REFERENCES imports(hash), source_row INTEGER NOT NULL, name TEXT, location TEXT, kms TEXT, mode TEXT, issues TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0, UNIQUE(import_hash,source_row));
CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY, happened_at TEXT NOT NULL, reason TEXT NOT NULL, details TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL REFERENCES employees(id), location_id INTEGER NOT NULL REFERENCES locations(id), valid_from TEXT NOT NULL, kms TEXT NOT NULL, mode TEXT NOT NULL, change_id INTEGER NOT NULL REFERENCES changes(id), UNIQUE(employee_id,location_id,valid_from));
'''


class Store:
    def __init__(self,path: str | Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:db.executescript(SCHEMA)
        self.path.chmod(0o600)

    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @contextmanager
    def transaction(self,revision=None):
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if revision is not None and db.execute('SELECT revision FROM meta').fetchone()[0]!=revision:
                raise ValueError('Gegevens zijn intussen gewijzigd. Vernieuw het scherm en controleer opnieuw.')
            yield db
            db.execute('UPDATE meta SET revision=revision+1')
            db.commit()
        except Exception:
            db.rollback(); raise
        finally:db.close()

    @staticmethod
    def location(db,name):
        name=required(name)
        db.execute('INSERT OR IGNORE INTO locations(name,name_key) VALUES(?,?)',(name,norm(name)))
        return db.execute('SELECT id FROM locations WHERE name_key=?',(norm(name),)).fetchone()[0]

    @staticmethod
    def audit(db,reason,details):
        return db.execute('INSERT INTO changes(happened_at,reason,details) VALUES(?,?,?)',
            (datetime.now(timezone.utc).isoformat(),required(reason),json.dumps(details,ensure_ascii=False))).lastrowid

    @staticmethod
    def add_version(db,employee,location,kms,mode,start,change):
        start=valid_day(start); kms=distance(kms)
        if mode not in MODES:raise ValueError('Kies een geldige vervoerswijze.')
        if not db.execute('SELECT id FROM employees WHERE id=?',(employee,)).fetchone():
            raise ValueError('Onbekende werknemer.')
        if not db.execute('SELECT id FROM locations WHERE id=?',(location,)).fetchone():
            raise ValueError('Onbekende locatie.')
        previous=db.execute('SELECT max(valid_from) FROM settings WHERE employee_id=? AND location_id=?',(employee,location)).fetchone()[0]
        if previous is not None and start<=previous:
            raise ValueError('Nieuwe ingangsdatum moet na de nieuwste versie liggen; historie wordt niet overschreven.')
        db.execute('INSERT INTO settings(employee_id,location_id,valid_from,kms,mode,change_id) VALUES(?,?,?,?,?,?)',
            (employee,location,start,kms,mode,change))

    def seed_reference(self,result):
        with self.transaction() as db:
            digest=result.report.source_sha256
            if db.execute('SELECT 1 FROM imports WHERE hash=?',(digest,)).fetchone():return 0
            db.execute('INSERT INTO imports VALUES(?)',(digest,))
            for r in result.records:
                db.execute('INSERT INTO candidates(import_hash,source_row,name,location,kms,mode,issues) VALUES(?,?,?,?,?,?,?)',
                    (digest,r.source_row,r.employee_name,r.location,str(r.distance) if r.distance is not None else None,
                     r.transport_mode,json.dumps(r.unresolved)))
            return len(result.records)

    def confirm_reference(self,start):
        """Trust reference names/values in bulk, without guessing missing fields.

        Name equality groups rows inside the reference only, never Planet IDs.
        Canonical-location conflicts are checked before any version is activated.
        Existing settings (including relocations) are never overwritten.
        """
        start=valid_day(start)
        counts={'employees_created':0,'settings_created':0,'rows_confirmed':0,'rows_pending':0}
        with self.transaction() as db:
            rows=list(db.execute('SELECT * FROM candidates WHERE reviewed=0 ORDER BY id'))
            employee_ids={}
            groups={}
            for row in rows:
                if not row['name'] or not row['name'].strip():continue
                key=norm(row['name'])
                if key not in employee_ids:
                    matches=[e['id'] for e in db.execute('SELECT * FROM employees') if norm(e['name'])==key]
                    if len(matches)>1:
                        employee_ids[key]=None
                    elif matches:employee_ids[key]=matches[0]
                    else:
                        employee_ids[key]=db.execute('INSERT INTO employees(name) VALUES(?)',(required(row['name']),)).lastrowid
                        counts['employees_created']+=1
                if not row['location'] or not row['location'].strip():continue
                alias=db.execute("SELECT location_id FROM aliases WHERE source='reference' AND name_key=?",(norm(row['location']),)).fetchone()
                loc=alias[0] if alias else self.location(db,row['location'])
                db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?)',('reference',norm(row['location']),loc))
                groups.setdefault((key,loc),[]).append(row)
            change=None
            for (key,loc),members in groups.items():
                employee=employee_ids[key]
                values=set()
                for row in members:
                    if row['kms'] is not None and row['mode'] in MODES:
                        values.add((Decimal(row['kms']),row['mode']))
                # Do not allow one complete row to silently defeat an incomplete
                # or conflicting row for the same employee/physical location.
                if employee is None or len(values)!=1 or any(r['kms'] is None or r['mode'] not in MODES for r in members):continue
                kms,mode=next(iter(values))
                existing=list(db.execute('SELECT * FROM settings WHERE employee_id=? AND location_id=?',(employee,loc)))
                if existing:
                    if not any(s['valid_from']==start and Decimal(s['kms'])==kms and s['mode']==mode for s in existing):continue
                else:
                    if change is None:change=self.audit(db,'Sociaal-abo-basisgegevens automatisch bevestigd',{'valid_from':start})
                    self.add_version(db,employee,loc,kms,mode,start,change)
                    counts['settings_created']+=1
                for row in members:
                    db.execute('UPDATE candidates SET reviewed=1 WHERE id=?',(row['id'],))
                    counts['rows_confirmed']+=1
            if counts['employees_created'] and change is None:
                self.audit(db,'Werknemers uit Sociaal abo aangemaakt',{'count':counts['employees_created']})
            counts['rows_pending']=db.execute('SELECT count(*) FROM candidates WHERE reviewed=0').fetchone()[0]
        return counts

    def register_planet(self,cleaned):
        names={}
        for m in cleaned.movements:
            for s in m.source_shifts:
                name=f'{s.last_name} {s.first_name}'
                if s.employee_id in names and norm(names[s.employee_id])!=norm(name):
                    raise ValueError('Pl@net-ID bevat verschillende namen; handmatige controle vereist.')
                names[s.employee_id]=name
        with self.transaction() as db:
            for planet_id,name in names.items():
                previous=db.execute('SELECT name FROM planet_agents WHERE planet_id=?',(planet_id,)).fetchone()
                if previous and norm(previous['name'])!=norm(name):
                    raise ValueError('Bestaand Pl@net-ID heeft een gewijzigde naam; controleer identiteit.')
                db.execute('INSERT OR IGNORE INTO planet_agents(planet_id,name) VALUES(?,?)',(planet_id,name))
        return len(names)

    def bootstrap_locations(self,rules):
        with self.transaction() as db:
            airport=self.location(db,'LUCHTHAVEN')
            db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?)',('reference','apt',airport))
            for rule in rules:
                # Dated rules stay in TOML for historical cleaning; only undated
                # rules are copied to the current management alias list.
                if rule.valid_from==date.min and rule.valid_until==date.max:
                    loc=self.location(db,rule.location)
                    old=db.execute('SELECT location_id FROM aliases WHERE source=? AND name_key=?',('planet',norm(rule.customer))).fetchone()
                    if old and old[0]!=loc:raise ValueError('Locatieconfiguratie conflicteert met opgeslagen alias.')
                    db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?)',('planet',norm(rule.customer),loc))

    def apply(self,action,data,revision):
        if type(revision) is not int:raise ValueError('Schermversie ontbreekt; vernieuw eerst.')
        with self.transaction(revision) as db:
            if action=='employee':
                name=required(data.get('name'))
                employee=db.execute('INSERT INTO employees(name) VALUES(?)',(name,)).lastrowid
                self.audit(db,'Nieuwe werknemer',{'employee_id':employee})
            elif action=='link':
                employee=data.get('employee_id'); planet=required(data.get('planet_id'))
                agent=db.execute('SELECT * FROM planet_agents WHERE planet_id=?',(planet,)).fetchone()
                if not agent or agent['employee_id'] is not None:raise ValueError('Agent ontbreekt of is al gekoppeld.')
                if not db.execute('SELECT id FROM employees WHERE id=?',(employee,)).fetchone():raise ValueError('Onbekende werknemer.')
                db.execute('UPDATE planet_agents SET employee_id=? WHERE planet_id=?',(employee,planet))
                self.audit(db,'Handmatige agentkoppeling',{'planet_id':planet,'employee_id':employee})
            elif action=='location':
                self.location(db,data.get('name'))
                self.audit(db,'Locatie toegevoegd',{'name':required(data.get('name'))})
            elif action=='alias':
                source=data.get('source'); alias=required(data.get('name')); loc=data.get('location_id')
                if source not in ('reference','planet'):raise ValueError('Kies referentie of Pl@net als bron.')
                if not db.execute('SELECT id FROM locations WHERE id=?',(loc,)).fetchone():raise ValueError('Onbekende locatie.')
                old=db.execute('SELECT location_id FROM aliases WHERE source=? AND name_key=?',(source,norm(alias))).fetchone()
                if old:raise ValueError('Alias bestaat al; wijzig een historische koppeling niet stilzwijgend.')
                db.execute('INSERT INTO aliases VALUES(?,?,?)',(source,norm(alias),loc))
                self.audit(db,'Handmatige locatiealias',data)
            elif action in ('ignore_candidate','restore_candidate'):
                candidate=data.get('candidate_id')
                if type(candidate) is not int:raise ValueError('Kies een geldige bronregel.')
                row=db.execute('SELECT reviewed FROM candidates WHERE id=?',(candidate,)).fetchone()
                expected=0 if action=='ignore_candidate' else 2
                if not row or row[0]!=expected:raise ValueError('Bronregel ontbreekt of heeft intussen een andere status.')
                reason=required(data.get('reason','')) if action=='ignore_candidate' else 'Genegeerde bronregel teruggezet naar Nakijken'
                self.audit(db,reason,{'action':action,'candidate_id':candidate})
                # reviewed: 0=pending, 1=confirmed, 2=ignored. Keep source
                # values and active employee/location settings untouched.
                db.execute('UPDATE candidates SET reviewed=? WHERE id=?',(2 if action=='ignore_candidate' else 0,candidate))
            elif action in ('setting','candidate'):
                if action=='candidate':
                    row=db.execute('SELECT reviewed FROM candidates WHERE id=?',(data.get('candidate_id'),)).fetchone()
                    if not row or row[0]:raise ValueError('Startregel ontbreekt of is al beoordeeld.')
                change=self.audit(db,data.get('reason',''),data)
                self.add_version(db,data.get('employee_id'),data.get('location_id'),data.get('kms'),data.get('mode'),data.get('valid_from'),change)
                if action=='candidate':db.execute('UPDATE candidates SET reviewed=1 WHERE id=?',(data['candidate_id'],))
            elif action=='relocation':
                employee=data.get('employee_id'); start=valid_day(data.get('valid_from'))
                updates=data.get('updates')
                if not isinstance(updates,list) or not updates:raise ValueError('Vul alle locaties opnieuw in.')
                expected={r[0] for r in db.execute('SELECT DISTINCT location_id FROM settings WHERE employee_id=?',(employee,))}
                actual=[u.get('location_id') for u in updates if isinstance(u,dict)]
                if len(actual)!=len(updates) or len(actual)!=len(set(actual)) or set(actual)!=expected:
                    raise ValueError('Verhuizing vereist precies alle bestaande locaties van deze werknemer.')
                change=self.audit(db,data.get('reason',''),data)
                for u in updates:self.add_version(db,employee,u['location_id'],u.get('kms'),u.get('mode'),start,change)
            else:raise ValueError('Onbekende actie.')

    def resolve(self,employee,location,day):
        day=valid_day(day)
        with self.connect() as db:
            r=db.execute('SELECT * FROM settings WHERE employee_id=? AND location_id=? AND valid_from<=? ORDER BY valid_from DESC LIMIT 1',(employee,location,day)).fetchone()
            return dict(r) if r else None

    def snapshot(self):
        with self.connect() as db:
            return {**{name:[dict(r) for r in db.execute(f'SELECT * FROM {name} ORDER BY 1')] for name in
                       ('employees','locations','aliases','planet_agents','candidates','settings','changes')},
                    'revision':db.execute('SELECT revision FROM meta').fetchone()[0]}

    def backup(self,target):
        target=Path(target)
        if target.exists():raise ValueError('Backupbestand bestaat al; wordt niet overschreven.')
        target.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as source,sqlite3.connect(target) as destination:source.backup(destination)
        target.chmod(0o600)

    def cleaning_policy(self,policy):
        from dataclasses import replace
        aliases=dict(policy.location_aliases)
        dated_customers={r.customer for r in policy.location_rules}
        with self.connect() as db:
            for row in db.execute("SELECT a.name_key,l.name FROM aliases a JOIN locations l ON l.id=a.location_id WHERE a.source='planet'"):
                customer,location=row
                if customer in dated_customers:
                    matches={r.location for r in policy.location_rules if r.customer==customer}
                    if matches!={location}:raise ValueError('Beheeralias conflicteert met historische TOML-locatieregels.')
                    continue
                if customer in aliases and aliases[customer]!=location:raise ValueError('Conflicterende locatiealias.')
                aliases[customer]=location
            revision=db.execute('SELECT revision FROM meta').fetchone()[0]
        return replace(policy,location_aliases=tuple(aliases.items()),
                       location_config_version=f'{policy.location_config_version}/db-revision-{revision}')
