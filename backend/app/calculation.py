"""Phase 5: auditable ordinary-car daily amounts, not payroll-ready totals."""
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from app.distances import whole_kms


def mode_key(mode):
    return ' '.join((mode or '').casefold().split())


def number(value):
    if not isinstance(value,str) or len(value)>100:raise ValueError('Vul een geldig bedrag als tekst in.')
    try:value=Decimal(value.strip().replace(',','.'))
    except InvalidOperation:raise ValueError('Ongeldig bedrag.') from None
    if not value.is_finite() or value<0 or value>Decimal('100000'):raise ValueError('Bedrag buiten toegestaan bereik.')
    return value


def validate_tariff(data):
    """Require a complete continuous integer-km table; never infer gaps."""
    bands=data.get('bands')
    if not isinstance(bands,list) or not bands or len(bands)>100:raise ValueError('Vul de volledige tarieftabel in.')
    validated=[];expected=1
    for band in bands:
        if not isinstance(band,dict):raise ValueError('Ongeldige tariefregel.')
        lo,hi=band.get('from_km'),band.get('to_km')
        if type(lo) is not int or type(hi) is not int or lo!=expected or hi<lo or hi>60:
            raise ValueError('Tariefregels moeten zonder gaten of overlap van 1 tot 60 km lopen.')
        amount=number(band.get('amount'))
        if amount!=amount.quantize(Decimal('.01')):raise ValueError('Gebruik maximaal twee decimalen per tabelbedrag.')
        validated.append({'from_km':lo,'to_km':hi,'amount':format(amount,'.2f')});expected=hi+1
    if expected!=61:raise ValueError('De tabel moet alle afstanden van 1 tot 60 km bevatten.')
    extra=number(data.get('extra_per_km'))
    if extra!=extra.quantize(Decimal('.0001')):raise ValueError('Gebruik maximaal vier decimalen voor het extra km-bedrag.')
    return {'bands':validated,'extra_per_km':str(extra)}


def pdf_start_tariff():
    amounts=('3.43','3.43','3.43','3.74','4.02','4.30','4.53','4.81','5.05','5.32',
             '5.56','5.84','6.07','6.34','6.60','6.86','7.11','7.38','7.61','7.89',
             '8.14','8.41','8.59','8.93','9.10','9.44','9.60','9.96','10.13','10.48')
    bands=[{'from_km':i,'to_km':i,'amount':amount} for i,amount in enumerate(amounts,1)]
    for lo,amount in zip(range(31,59,3),('10.81','11.49','12.19','12.70','13.39','14.08','14.76','15.10','15.63','15.96')):
        bands.append({'from_km':lo,'to_km':lo+2,'amount':amount})
    return validate_tariff({'bands':bands,'extra_per_km':'0.31'})


def pdf_special_tariff():
    amounts=('4.29','4.29','4.29','4.68','5.03','5.37','5.66','6.01','6.31','6.66',
             '6.96','7.29','7.59','7.93','8.24','8.59','8.89','9.22','9.52','9.87',
             '10.18','10.52','10.73','11.16','11.38','11.81','12.01','12.45','12.66','13.09')
    bands=[{'from_km':i,'to_km':i,'amount':a} for i,a in enumerate(amounts,1)]
    for lo,a in zip(range(31,59,3),('13.51','14.36','15.24','15.88','16.73','17.60','18.46','18.89','19.54','19.96')):
        bands.append({'from_km':lo,'to_km':lo+2,'amount':a})
    return validate_tariff({'bands':bands,'extra_per_km':'0.31'})


def validate_km_rate(value):
    rate=number(value)
    if rate!=rate.quantize(Decimal('.0001')):raise ValueError('Gebruik maximaal vier decimalen voor het kilometertarief.')
    return str(rate)


def calculate_movement(movement,tariffs,special_tariffs=None,extra_shift_tariffs=None):
    result={'movement_id':movement['id'],'status':'BLOCKED','amount':None,'reason':'',
            'route_id':None,'distance':None,'distance_valid_from':None,'tariff_id':None,
            'tariff_valid_from':None,'tariff_source':None,'rule':None}
    def stop(status,reason):
        return {**result,'status':status,'reason':reason}
    if movement['status']!='MATCHED':return stop('BLOCKED','Naam- of locatiekoppeling eerst oplossen.')
    routes=movement['routes'];modes={mode_key(r['mode']) for r in routes}
    if 'telework' in modes:return stop('EXCLUDED_TELEWORK','Telework: geen verplaatsing en geen kilometervergoeding.')
    if 'dienstwagen' in modes:return stop('EXCLUDED_COMPANY_CAR','Dienstwagen: geen kilometervergoeding.')
    cars=[r for r in routes if mode_key(r['mode']) in ('auto','privé auto')]
    if cars and 'trein' in modes:return stop('BLOCKED','Auto én trein op dezelfde locatie: vervoerskeuze eerst bevestigen.')
    if not cars:
        if modes=={'trein'}:return stop('EXCLUDED_TRAIN','Trein: n.v.t.; geen kilometervergoeding.')
        if modes=={'mob budget'}:return stop('EXCLUDED_MOBILITY_BUDGET','Mobiliteitsbudget: geen kilometervergoeding.')
        if not routes:return stop('BLOCKED','Geen vervoersroute geldig op de prestatiedatum.')
        return stop('LATER_PHASE','Geen gewone autoroute; vervoerswijze nog niet berekend.')
    if len(cars)!=1:return stop('BLOCKED','Meerdere autoroutes: geen willekeurige afstand kiezen.')
    if movement.get('phase5_special') is None:return stop('BLOCKED','Oud overzicht: vernieuwen voor controle speciale shiften.')
    special=False
    extra48=movement.get('extra_shift_48h') is True
    if special_tariffs is not None:
        if extra48 and extra_shift_tariffs is None:return stop('LATER_PHASE','48h-oproep: aparte regel, geen automatisch vroeg/laat-tarief.')
        if not extra48 and movement.get('early_late') is None and movement['phase5_special']:
            return stop('BLOCKED','Vernieuw de shiften om vroeg/laat en 48h apart te controleren.')
        special=movement.get('early_late') is True
        if special:tariffs=special_tariffs
    elif movement['phase5_special']:return stop('LATER_PHASE','Start tussen 22:00 en 06:00 of 48h: speciale autologica in fase 6.')
    result['tariff_kind']='EXTRA48' if extra48 else 'SPECIAL' if special else 'STANDARD'
    route=cars[0]
    try:km=Decimal(whole_kms(number(route['kms'])))
    except ValueError:return stop('BLOCKED','Geen geldige enkele afstand voor auto.')
    if km<1:return stop('BLOCKED','Afstand onder 1 km: geen bevestigde tariefregel.')
    if extra48:
        effective=[t for t in (extra_shift_tariffs or []) if t['valid_from']<=movement['day']]
        if not effective:return stop('BLOCKED','Geen 48h-kilometertarief geldig op de prestatiedatum.')
        tariff=max(effective,key=lambda t:(t['valid_from'],t['id']))
        rate=Decimal(validate_km_rate(tariff['rate_per_km']));total_km=km*2
        result.update(status='CALCULATED',amount=format((total_km*rate).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'),
            reason='48h-extra-shift; heen en terug; apart kilometertarief, geen standaard/vroeg-laat-bedrag erbij.',
            route_id=route['route_id'],distance=str(km),reimbursed_kms=str(total_km),distance_factor=2,
            distance_valid_from=route['valid_from'],tariff_id=tariff['id'],tariff_valid_from=tariff['valid_from'],
            tariff_source=tariff['source'],rate_per_km=str(rate),rule=f'{km} km × 2 × €{rate}/km')
        return result
    effective=[t for t in tariffs if t['valid_from']<=movement['day']]
    if not effective:return stop('BLOCKED','Geen autotarief geldig op de prestatiedatum.')
    tariff=max(effective,key=lambda t:(t['valid_from'],t['id']))
    data=tariff['data'];lookup=min(km,Decimal(60))
    band=next((b for b in data['bands'] if b['from_km']<=lookup<=b['to_km']),None)
    if band is None:return stop('BLOCKED','Afstand ontbreekt in tarieftabel.')
    base=Decimal(band['amount']);extra=max(km-60,Decimal(0))*Decimal(data['extra_per_km'])
    result.update(status='CALCULATED',amount=format((base+extra).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'),
        reason=('Vroeg/laat auto; alleen startuur; speciale tabel.' if special else 'Gewone auto; enkele afstand; 120% zit al in tabelbedrag.'),route_id=route['route_id'],
        distance=str(km),distance_valid_from=route['valid_from'],tariff_id=tariff['id'],
        tariff_valid_from=tariff['valid_from'],tariff_source=tariff['source'],
        rule=f"{band['from_km']}–{band['to_km']} km: €{base:.2f}"+(f" + {km-60} × €{data['extra_per_km']}" if km>60 else ''))
    return result


def calculate_month(movements,tariffs):
    rows=[calculate_movement(m,tariffs) for m in movements]
    return {'rows':rows,'statuses':dict(Counter(r['status'] for r in rows)),
        'payroll_ready':False,'warning':'Controlebedragen per beweging, geen uitbetalingsbestand. Speciale regels en weekmaximum/onderbroken-dienstbehandeling zijn nog niet verwerkt.'}
