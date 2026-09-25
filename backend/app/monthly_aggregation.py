"""Phase 9: aggregate calculated movement details without hiding blockers."""
from collections import Counter
from decimal import Decimal

EXCLUDED={'EXCLUDED_TRAIN','EXCLUDED_COMPANY_CAR','EXCLUDED_MOBILITY_BUDGET','EXCLUDED_TELEWORK'}


def aggregate(payload,rows):
    agents={a['planet_id']:a for a in payload['agents']}
    movements={m['id']:m for m in payload['movements']}
    groups={}
    for row in rows:
        movement=movements[row['movement_id']];agent=agents[movement['planet_id']]
        key=agent.get('worker_id') or 'planet:'+movement['planet_id']
        group=groups.setdefault(key,{'worker_id':agent.get('worker_id'),'planet_id':movement['planet_id'],
            'name':agent.get('worker_name') or ' / '.join(agent.get('source_names',[])),
            'total':Decimal('0'),'statuses':Counter(),'shifts':[]})
        group['statuses'][row['status']]+=1
        if row['status']=='CALCULATED' and row.get('amount') is not None:group['total']+=Decimal(row['amount'])
        group['shifts'].append({'movement_id':movement['id'],'date':movement['day'],
            'location':movement.get('location') or movement.get('source_location'),'status':row['status'],
            'mode':row.get('selected_mode'),'distance':row.get('distance'),'rule':row.get('rule'),
            'amount':row.get('amount'),'amount_source':row.get('amount_source'),'reason':row.get('reason'),
            'original_amount':row.get('original_amount'),'amount_override_reason':row.get('amount_override_reason'),
            'reimbursed_kms':row.get('reimbursed_kms'),'distance_factor':row.get('distance_factor'),
            'distance_source':row.get('distance_source'),'distance_valid_from':row.get('distance_valid_from'),
            'tariff_kind':row.get('tariff_kind'),'tariff_id':row.get('tariff_id'),
            'tariff_valid_from':row.get('tariff_valid_from'),'tariff_source':row.get('tariff_source'),
            'rate_per_km':row.get('rate_per_km'),'override_reason':row.get('override_reason'),
            'extra_shift_48h':movement.get('extra_shift_48h') is True,
            'early_late':movement.get('early_late') is True,
            'source_shifts':movement.get('source_shifts',[])})
    employees=[]
    for group in groups.values():
        blocking=group['statuses']['BLOCKED']+group['statuses']['LATER_PHASE']
        group.update(total=format(group['total'].quantize(Decimal('.01')),'.2f'),statuses=dict(group['statuses']),
                     blocking=blocking,ready=blocking==0)
        group['shifts'].sort(key=lambda r:(r['date'],r['movement_id']));employees.append(group)
    employees.sort(key=lambda r:r['name'])
    statuses=Counter(r['status'] for r in rows);blocking=statuses['BLOCKED']+statuses['LATER_PHASE']
    return {'employees':employees,'employee_count':len(employees),
        'calculated_total':format(sum((Decimal(r['amount']) for r in rows if r['status']=='CALCULATED' and r.get('amount') is not None),Decimal('0')).quantize(Decimal('.01')),'.2f'),
        'statuses':dict(statuses),'blocking':blocking,'ready':blocking==0,
        'excluded':sum(statuses[s] for s in EXCLUDED),
        'warning':None if blocking==0 else f'{blocking} beweging(en) blokkeren de finale maandafsluiting.'}
