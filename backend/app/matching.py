"""Phase 4: deterministic identity/location linking, never fuzzy auto-binding."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
import json
import unicodedata

from app.cleaning import CleaningPolicy, clean_import
from app.cleaning.locations import load_location_rules
from app.transport import km_applicable
from app.calculation import calculate_month
from datetime import time


def key(value):
    return ' '.join(unicodedata.normalize('NFKC',value or '').casefold().split())


def configuration_digest(config):
    values={k:config.get(k,[]) for k in ('workers','routes','versions','employee_links','location_links','car_tariffs','transport_defaults')}
    values['calculation_policy']='phase6-start-only-separate-48h-default-car-coverage-v5'
    return sha256(json.dumps(values,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def suggestions(names,workers):
    ranked=sorted(((max(SequenceMatcher(None,n,key(w['name'])).ratio() for n in names),w) for w in workers),key=lambda pair:(-pair[0],pair[1]['id']))
    return [{'worker_id':w['id'],'name':w['name']} for score,w in ranked[:3] if score>=.65]


def match_import(imported,config,location_config):
    if imported.has_errors:raise ValueError('Los de Pl@net-importfouten eerst op.')
    if not imported.report.selected_month:raise ValueError('Kies expliciet één maand voor fase 4.')
    version,rules=load_location_rules(location_config)
    confirmed={key(r['customer']):r['location'] for r in config.get('location_links',[])}
    aliases={}
    # Explicit dashboard confirmations feed phase 2 as well: customers that
    # share a confirmed physical site must not become extra trips.
    for shift in imported.shifts:
        target=confirmed.get(key(shift.customer))
        if target is None:continue
        existing=[r for r in rules if r.customer==shift.customer.strip().casefold()]
        if existing:
            if any(key(r.location)!=key(target) for r in existing):raise ValueError('Koppeling conflicteert met bestaande fysieke locatieregels.')
        else:aliases[shift.customer.strip().casefold()]=target
    policy=CleaningPolicy(location_aliases=tuple(aliases.items()),location_rules=rules,location_config_version=version)
    cleaned=clean_import(imported,policy=policy)
    workers=config['workers'];workers_by_id={w['id']:w for w in workers}
    by_name=defaultdict(set)
    for w in workers:by_name[key(w['name'])].add(w['id'])
    source_agents=defaultdict(list)
    for movement in cleaned.movements:
        for s in movement.source_shifts:source_agents[s.employee_id].append(s)
    links={r['planet_id']:r for r in config.get('employee_links',[])}
    agents={}
    for planet_id,shifts in source_agents.items():
        names=sorted({f'{s.last_name} {s.first_name}'.strip() for s in shifts})
        signatures=sorted({key(f'{s.last_name} {s.first_name}') for s in shifts})
        candidates=set()
        for s in shifts:
            candidates.update(by_name.get(key(f'{s.last_name} {s.first_name}'),set()))
            candidates.update(by_name.get(key(f'{s.first_name} {s.last_name}'),set()))
        link=links.get(planet_id);method='NORMALIZED_NAME';worker_id=None
        if link:
            method='CONFIRMED_PLANET_ID'
            if json.loads(link['source_keys'])==signatures and link['worker_id'] in workers_by_id:
                worker_id=link['worker_id'];status='MATCHED'
            else:status='AMBIGUOUS'
        elif len(signatures)>1 or len(candidates)>1:status='AMBIGUOUS'
        elif len(candidates)==1:worker_id=next(iter(candidates));status='MATCHED'
        else:status='UNMATCHED_EMPLOYEE'
        agents[planet_id]={'planet_id':planet_id,'source_names':names,'source_keys':signatures,'worker_id':worker_id,
            'worker_name':workers_by_id[worker_id]['name'] if worker_id is not None else None,'status':status,'method':method,
            'suggestions':suggestions(signatures,workers) if status!='MATCHED' else []}
    # Two distinct Planet IDs with the same normalized name cannot silently
    # become one person. Explicit confirmed-ID bindings are needed in that case.
    targets=defaultdict(list)
    for agent in agents.values():
        if agent['worker_id'] is not None:targets[agent['worker_id']].append(agent)
    for group in targets.values():
        if len(group)>1:
            for agent in group:
                if agent['method']!='CONFIRMED_PLANET_ID':agent.update(worker_id=None,worker_name=None,status='AMBIGUOUS')
    location_index=defaultdict(set)
    for route in config['routes']:location_index[key(route['location'])].add(route['location'])
    movements=[];locations={}
    for index,m in enumerate(cleaned.movements,1):
        first=m.source_shifts[0];agent=agents[first.employee_id]
        matches=location_index.get(key(m.physical_location),set())
        # Distinct stored spellings normalized to one site are one matching
        # location, but all relevant route alternatives remain available.
        location=sorted(matches)[0] if matches else None
        location_status='MATCHED' if location is not None else 'UNMATCHED_LOCATION'
        route_ids={r['id'] for r in config['routes'] if r['worker_id']==agent['worker_id'] and key(r['location'])==key(location) and location is not None}
        available=[]
        for r in config['routes']:
            if r['id'] not in route_ids:continue
            versions=[v for v in config['versions'] if v['route_id']==r['id'] and v['valid_from']<=first.day.isoformat()]
            if versions:
                v=max(versions,key=lambda v:v['valid_from'])
                applicable=km_applicable(r['mode'])
                from app.distances import whole_kms
                available.append({'route_id':r['id'],'mode':r['mode'],'kms':str(whole_kms(v['kms'])) if applicable and v['kms'] is not None else None,'km_applicable':applicable,'valid_from':v['valid_from']})
        from app.transport_defaults import effective as effective_transport
        default=effective_transport(config.get('transport_defaults',[]),agent['worker_id'],location,first.day.isoformat()) if agent['worker_id'] is not None and location is not None else None
        if default:
            selected=[r for r in available if key(r['mode'])==key(default['mode'])]
            available=selected or [{'route_id':None,'mode':default['mode'],'kms':None,'km_applicable':default['mode'] in ('Privé auto','Fiets'),'valid_from':default['valid_from']}]
        if agent['status']!='MATCHED':status=agent['status']
        elif location_status!='MATCHED':status=location_status
        elif not route_ids and not default:status='UNMATCHED_EMPLOYEE_LOCATION'
        else:status='MATCHED'
        movements.append({'id':index,'planet_id':first.employee_id,'day':first.day.isoformat(),'source_location':m.physical_location,
            'location':location,'employee_status':agent['status'],'location_status':location_status,'status':status,
            'routes':available,'route_status':'AVAILABLE' if available else 'NO_EFFECTIVE_ROUTE',
            'phase5_special':any(s.start_time<time(6) or s.start_time>=time(22)
                or (s.remark or '').strip().casefold()=='48h_icts_extra_shift'
                for s in m.source_shifts),
            'early_late':any(s.start_time<time(6) or s.start_time>=time(22) for s in m.source_shifts),
            'extra_shift_48h':any((s.remark or '').strip().casefold()=='48h_icts_extra_shift' for s in m.source_shifts),
            'source_shifts':[{'row':s.source_row,'customer':s.customer,'task':s.task,'start':s.start_time.isoformat(timespec='minutes'),
                'end':s.end_time.isoformat(timespec='minutes'),'end_day_offset':s.end_time_day_offset} for s in m.source_shifts]})
        for s in m.source_shifts:
            locations[s.customer]={'customer':s.customer,'physical_location':m.physical_location,'reference_location':location,'status':location_status}
    report=cleaned.report
    excluded_rows={r.shift.source_row for r in cleaned.removals if r.reason in ('GHOST_AGENT','TELEWORK','CONFIRMED_EXCLUDED_REMARK')}
    # Duplicate source shifts remain evidence inside each physical movement.
    source_manifest=[{'row':s.source_row,'planet_id':s.employee_id} for s in imported.shifts if s.source_row not in excluded_rows]
    return {'month':imported.report.selected_month,'created_at':datetime.now(timezone.utc).isoformat(),'source_sha256':imported.report.source_sha256,
        'source_manifest':source_manifest,
        'calculation':calculate_month(movements,config.get('car_tariffs',[])),
        'configuration_digest':configuration_digest(config),'agents':list(agents.values()),'locations':sorted(locations.values(),key=lambda r:r['customer']),
        'movements':movements,'summary':{'agents':len(agents),'movements':len(movements),'source_shifts':sum(len(m.source_shifts) for m in cleaned.movements),
            'statuses':dict(Counter(m['status'] for m in movements)),'input_rows':report.input_rows,'ghosts':report.ghost_agent_rows,
            'telework':report.telework_rows,'duplicates':report.duplicate_rows},'location_rules_version':version}
