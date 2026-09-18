"""Simple ordinary-car control amounts from cached routes; never call Mapbox."""
from collections import Counter,defaultdict
from copy import deepcopy
from app.calculation import calculate_movement,mode_key
from app.importers.reference import norm
from app.route_corrections import effective_distance
from app.routing import plan


def calculate_cached_month(db,config,run_id,payload):
    movements=deepcopy(payload['movements'])
    agents={a['planet_id']:a for a in payload['agents']}
    from app.itinerary import itineraries
    journeys=itineraries(payload)
    sites=defaultdict(set)
    for m in movements:
        wid=agents[m['planet_id']].get('worker_id')
        leg=journeys.get((m['planet_id'],m['day'],m['id']),{})
        m['multi_location']=leg.get('multi_location',False)
        m['origin_location']=leg.get('origin_location')
        sites[(wid or m['planet_id'],m['day'])].add(norm(m.get('location') or m['source_location']))
    lookup={};plan_error=None
    try:
        prepared=plan(db,config,run_id)
        for route in prepared['routes']:
            if route['profile']!='driving':continue
            for c in route['contexts']:
                lookup[(c['worker_id'],norm(c['location']),c['day'])]=(route,c)
    except ValueError as error:plan_error=str(error)
    results=[]
    for m in movements:
        wid=agents[m['planet_id']].get('worker_id')
        leg=journeys.get((m['planet_id'],m['day'],m['id']),{})
        cars=[r for r in m.get('routes',[]) if mode_key(r['mode']) in ('auto','privé auto')]
        selected=None;context=None
        if cars:
            # Explicit default: auto wins over optional bicycle/train/company modes.
            m['routes']=cars
            for car in cars:car['kms']=None
            route,context=lookup.get((wid,norm(m.get('location') or ''),m['day']),(None,None))
            if route and route['cached'] and route['cached']['status']=='READY':
                selected=effective_distance(route['cached'],wid)
                for car in cars:
                    car['kms']=selected['kms']
                    car['valid_from']=max(context['home_valid_from'],context['location_valid_from'],car['valid_from'])
        calculation_movement=deepcopy(m)
        if leg.get('origin_location'):
            calculation_movement.update(early_late=False,extra_shift_48h=False,phase5_special=False)
        result=calculate_movement(calculation_movement,config.get('car_tariffs',[]),config.get('special_car_tariffs',[]),config.get('extra_shift_tariffs',[]))
        result.update(multi_location=leg.get('multi_location',False),origin_location=leg.get('origin_location'),sequence=leg.get('sequence'))
        result.update(selected_mode='Auto' if cars else None,distance_source=selected['distance_source'] if selected else None,
                      travel_kms=selected['kms'] if selected else None,
                      mapbox_route_id=selected['id'] if selected else None,override_reason=selected.get('override_reason') if selected else None)
        if plan_error:
            result.update(status='BLOCKED',amount=None,reason=plan_error)
        elif leg.get('error'):
            result.update(status='LATER_PHASE',amount=None,reason=leg['error'])
        elif cars and not selected and result['status']=='BLOCKED' and m['status']=='MATCHED':
            result['reason']=('Tussenlocatieafstand ontbreekt: '+leg['origin_location']+' → '+m['location']+'. Vraag deze route eenmalig op via Werknemersroutes.' if leg.get('origin_location') else 'Geen bevestigde opgeslagen autoroute op deze datum. Geen fallback naar Sociaal-abo of Planet-kilometers.')
        if result['status']=='CALCULATED':
            if leg.get('origin_location'):result['reason']='Tussenlocatie '+leg['origin_location']+' → '+m['location']+'; enkele afstand; standaardtarieftabel.'
            result['reason']+=' Auto als standaard; '+('HR-correctie: '+selected['override_reason'] if selected['distance_source']=='HR' else 'opgeslagen Mapbox-afstand')+'.'
        results.append(result)
    return {'rows':results,'resolved_movements':movements,'statuses':dict(Counter(r['status'] for r in results)),
            'payroll_ready':False,'distance_policy':'cached-route-with-hr-override-ceil-auto-default',
            'warning':'Controleberekening auto: standaard/vroeg-laat of 48h. Meerdere locaties apart: eerste rit thuis, volgende rit locatie → locatie met standaardtabel. Overlap/onzekere volgorde blokkeert. Fietskeuze en weekmaximum volgen. Geen uitbetalingsbestand.'}
