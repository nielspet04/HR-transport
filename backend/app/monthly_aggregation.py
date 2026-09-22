"""Phase 9: aggregate calculated movement details without hiding blockers."""
from collections import Counter
from decimal import Decimal

EXCLUDED={'EXCLUDED_TRAIN','EXCLUDED_COMPANY_CAR','EXCLUDED_MOBILITY_BUDGET'}


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
            'amount':row.get('amount'),'amount_source':row.get('amount_source'),'reason':row.get('reason')})
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
