"""Simple ordinary-car control amounts from cached routes; never call Mapbox."""
from collections import Counter,defaultdict
from copy import deepcopy
from app.calculation import calculate_movement,mode_key
from app.importers.reference import norm
from app.route_corrections import effective_distance
from app.routing import plan
from decimal import Decimal,ROUND_HALF_UP
from app.distances import whole_kms
from app.calculation import validate_km_rate


def calculate_cached_month(db,config,run_id,payload):
    movements=deepcopy(payload['movements'])
    agents={a['planet_id']:a for a in payload['agents']}
    from app.itinerary import itineraries
    journeys=itineraries(payload)
    from app.shift_transport import choices as transport_choices
    overrides=transport_choices(db,payload)
    from app.calculation_corrections import corrections as amount_corrections
    amount_overrides=amount_corrections(db,payload)
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
            for c in route['contexts']:
                lookup[(c['worker_id'],norm(c['location']),c['day'],route['profile'])]=(route,c)
    except ValueError as error:plan_error=str(error)
    results=[]
    for m in movements:
        wid=agents[m['planet_id']].get('worker_id')
        leg=journeys.get((m['planet_id'],m['day'],m['id']),{})
        choice=overrides.get(m['id']);chosen=choice['mode'] if choice and choice['mode']!='DEFAULT' else None
        available=m.get('routes',[])
        if chosen=='AUTO':available=[{'route_id':None,'mode':'Privé auto','kms':None,'valid_from':m['day']}]
        elif chosen=='BIKE':available=[{'route_id':None,'mode':'Fiets','kms':None,'valid_from':m['day']}]
        elif chosen=='TRAIN':available=[{'route_id':None,'mode':'Trein','kms':None,'valid_from':m['day']}]
        cars=[r for r in available if mode_key(r['mode']) in ('auto','privé auto')]
        bikes=[r for r in available if mode_key(r['mode'])=='fiets']
        if cars and chosen!='BIKE':bikes=[]
        selected=None;context=None
        if cars:
            # Explicit default: auto wins over optional bicycle/train/company modes.
            m['routes']=cars
            for car in cars:car['kms']=None
            route,context=lookup.get((wid,norm(m.get('location') or ''),m['day'],'driving'),(None,None))
            if route and route['cached'] and route['cached']['status']=='READY':
                selected=effective_distance(route['cached'],wid)
                for car in cars:
                    car['kms']=selected['kms']
                    car['valid_from']=max(context['home_valid_from'],context['location_valid_from'],car['valid_from'])
        calculation_movement=deepcopy(m)
        calculation_movement['routes']=cars if cars else bikes if bikes else available
        if leg.get('origin_location'):
            # A transfer leg does not inherit an early/late supplement, but an
            # explicit 48h marker belongs to this actual shift and must survive.
            is_extra48=calculation_movement.get('extra_shift_48h') is True
            calculation_movement.update(early_late=False,phase5_special=is_extra48)
        result=calculate_movement(calculation_movement,config.get('car_tariffs',[]),config.get('special_car_tariffs',[]),config.get('extra_shift_tariffs',[]))
        if bikes:
            route,context=lookup.get((wid,norm(m.get('location') or ''),m['day'],'cycling'),(None,None));selected=None
            if route and route['cached'] and route['cached']['status']=='READY':selected=effective_distance(route['cached'],wid)
            if not selected:result.update(status='BLOCKED',amount=None,reason='Geen bevestigde opgeslagen fietsroute op deze datum.')
            else:
                effective=[t for t in config.get('bicycle_tariffs',[]) if t['valid_from']<=m['day']]
                if not effective:result.update(status='BLOCKED',amount=None,reason='Geen fietstarief geldig op de prestatiedatum.')
                else:
                    tariff=max(effective,key=lambda t:(t['valid_from'],t['id']));km=Decimal(whole_kms(selected['kms']));rate=Decimal(validate_km_rate(tariff['rate_per_km']));total=km*2
                    result.update(status='CALCULATED',amount=format((total*rate).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'),reason='Fiets: gewone fietsvergoeding heen en terug; geen vroeg/laat- of 48h-toeslag.',tariff_kind='BICYCLE',selected_mode='Fiets',distance=str(km),reimbursed_kms=str(total),distance_factor=2,distance_valid_from=max(context['home_valid_from'],context['location_valid_from']),tariff_id=tariff['id'],tariff_valid_from=tariff['valid_from'],tariff_source=tariff['source'],rate_per_km=str(rate),rule=f'{km} km × 2 × €{rate}/km',mapbox_route_id=selected['id'],distance_source=selected['distance_source'],override_reason=choice['reason'] if choice else None)
        result.update(multi_location=leg.get('multi_location',False),origin_location=leg.get('origin_location'),sequence=leg.get('sequence'),
                      gap_minutes=leg.get('gap_minutes'),journey_kind=leg.get('journey_kind'))
        result.update(selected_mode=result.get('selected_mode') or ('Auto' if cars else 'Trein' if chosen=='TRAIN' else None),distance_source=result.get('distance_source') or (selected['distance_source'] if selected else None),
                      travel_kms=selected['kms'] if selected else None,
                      mapbox_route_id=result.get('mapbox_route_id') or (selected['id'] if selected else None),override_reason=result.get('override_reason') or (choice['reason'] if choice else selected.get('override_reason') if selected else None))
        if plan_error:
            result.update(status='BLOCKED',amount=None,reason=plan_error)
        elif leg.get('error'):
            result.update(status='LATER_PHASE',amount=None,reason=leg['error'])
        elif cars and not selected and result['status']=='BLOCKED' and m['status']=='MATCHED':
            result['reason']=('Tussenlocatieafstand ontbreekt: '+leg['origin_location']+' → '+m['location']+'. Vraag deze route eenmalig op via Werknemersroutes.' if leg.get('origin_location') else 'Geen bevestigde opgeslagen autoroute op deze datum. Geen fallback naar Sociaal-abo of Planet-kilometers.')
        if result['status']=='CALCULATED':
            if result.get('tariff_kind')=='BICYCLE':
                result['reason']+=' '+('HR-afstandscorrectie: '+selected['override_reason'] if selected['distance_source']=='HR' else 'Opgeslagen Mapbox-fietsafstand.')
            else:
                if leg.get('origin_location') and result.get('tariff_kind')!='EXTRA48':result['reason']='Tussenlocatie '+leg['origin_location']+' → '+m['location']+'; enkele afstand; standaardtarieftabel.'
                result['reason']+=' Auto als standaard; '+('HR-correctie: '+selected['override_reason'] if selected['distance_source']=='HR' else 'opgeslagen Mapbox-afstand')+'.'
            correction=amount_overrides[m['id']
            ]
            result['amount_correction_history']=correction['history']
            if correction['active']:
                result.update(original_amount=result['amount'],amount=correction['active']['amount'],amount_source='HR',
                    amount_override_reason=correction['active']['reason'])
            else:result['amount_source']='BEREKEND'
        results.append(result)
    return {'rows':results,'resolved_movements':movements,'statuses':dict(Counter(r['status'] for r in results)),
            'payroll_ready':False,'distance_policy':'cached-route-with-hr-override-ceil-auto-default',
        'warning':'Controleberekening per gekozen vervoer. Fiets gebruikt uitsluitend het gewone gedateerde fietstarief, heen en terug, zonder vroeg/laat- of 48h-toeslag. Overlap/onzekere volgorde blokkeert. Weekmaximum volgt. Geen uitbetalingsbestand.'}
