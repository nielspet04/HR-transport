"""One-time bootstrap: name/location/km/mode only; no amounts or inheritance."""
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import re
from openpyxl import load_workbook
from app.models.reference import ReferenceRecord, ReferenceReport, ReferenceResult
from app.models.shift import ImportIssue
from .planet import ImportSourceError

HEADERS = ('Naam','Locatie','Afstand','Vervoerswijze')
MODES = {'privé auto':'PRIVATE_CAR','fiets':'BIKE','trein':'TRAIN','dienstwagen':'COMPANY_CAR'}


def norm(value) -> str:
    return ' '.join(value.strip().casefold().split()) if isinstance(value,str) else ''


def import_reference(path: str | Path, *, sheet_name='Report', route_aware=False) -> ReferenceResult:
    path = Path(path)
    try:
        digest = sha256(path.read_bytes()).hexdigest()
        book = load_workbook(path,read_only=True,data_only=False)
    except Exception:
        raise ImportSourceError('Cannot read reference workbook') from None
    try:
        if sheet_name not in book.sheetnames:
            raise ImportSourceError(f'Required reference sheet {sheet_name} missing')
        sheet = book[sheet_name]; sheet.reset_dimensions()
        try:
            rows = list(sheet.iter_rows())
        except Exception:
            raise ImportSourceError('Cannot parse reference sheet') from None
        mapping = None
        for index,row in enumerate(rows[:75]):
            names = [norm(c.value) for c in row]
            if {norm(k) for k in HEADERS} <= set(names):
                if any(names.count(norm(k))!=1 for k in HEADERS):
                    raise ImportSourceError('Duplicate required reference header')
                mapping = {k:names.index(norm(k)) for k in HEADERS}
                header = index+1
                break
        if mapping is None:
            raise ImportSourceError('Reference requires Naam, Locatie, Afstand, Vervoerswijze')
        records=[]; issues=[]
        blank=repeated=ignored=special=seen=0
        for number,row in enumerate(rows[header:],header+1):
            seen+=1
            if not any(c.value not in (None,'') for c in row):
                blank+=1; continue
            values={k:row[i].value if i<len(row) else None for k,i in mapping.items()}
            if all(norm(values[k])==norm(k) for k in HEADERS):
                repeated+=1; continue
            # Other fields and formulas are completely irrelevant to this schema.
            if all(values[k] in (None,'') for k in ('Locatie','Afstand','Vervoerswijze')):
                ignored+=1; continue
            if isinstance(values['Locatie'],str) and re.search(r'\b(vroeg|laat|suppl)\b',norm(values['Locatie'])):
                special+=1; continue
            unresolved=[]
            def warn(code,key):
                unresolved.append(code); issues.append(ImportIssue(code,'WARNING',number,key))
            invalid={k for k,i in mapping.items() if i<len(row) and row[i].data_type in ('f','e')}
            for k in invalid:warn('INVALID_SOURCE_FIELD',k)
            def text(key):
                if key in invalid:return None
                value=values[key]
                if isinstance(value,str) and value.strip():return value.strip()
                warn('MISSING_OR_INVALID_'+key.upper(),key); return None
            name=text('Naam'); location=text('Locatie')
            mode=text('Vervoerswijze')
            transport=mode if route_aware else MODES.get(norm(mode))
            if transport is None:warn('UNRESOLVED_TRANSPORT_MODE','Vervoerswijze')
            distance=None; value=values['Afstand']
            try:
                if 'Afstand' in invalid or isinstance(value,bool) or not isinstance(value,(str,int,float,Decimal)):
                    raise InvalidOperation
                if isinstance(value,str) and not re.fullmatch(r'\d+(?:[.,]\d+)?',value.strip()):raise InvalidOperation
                distance=Decimal(str(value).strip().replace(',','.'))
                if not distance.is_finite() or distance<0:raise InvalidOperation
            except InvalidOperation:
                distance=None
                if not (route_aware and norm(transport)=='trein'):warn('UNRESOLVED_DISTANCE','Afstand')
            records.append(ReferenceRecord(name,location,distance,transport,tuple(dict.fromkeys(unresolved)),tuple(values.items()),number))
        groups=defaultdict(list)
        for i,r in enumerate(records):
            if r.employee_name and r.location:
                key=(norm(r.employee_name),norm(r.location))
                if route_aware:key+=(norm(r.transport_mode),)
                groups[key].append(i)
        for indices in groups.values():
            if len({(records[i].distance,records[i].transport_mode) for i in indices})>1:
                for i in indices:
                    records[i]=replace(records[i],unresolved=records[i].unresolved+('CONFLICTING_PERSON_LOCATION',))
                    issues.append(ImportIssue('CONFLICTING_PERSON_LOCATION','WARNING',records[i].source_row,'Locatie'))
        return ReferenceResult(tuple(records),tuple(issues),ReferenceReport(header,seen,blank,repeated,ignored,special,len(records),sum(bool(r.unresolved) for r in records),digest))
    finally:
        book.close()
