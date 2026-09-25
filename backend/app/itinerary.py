"""Order physical movements conservatively; never infer an overlapping transfer."""
from collections import defaultdict
from datetime import datetime,timedelta
from app.importers.reference import norm

MAX_DIRECT_TRANSFER_GAP=timedelta(hours=2)


def itineraries(payload, excluded_movement_ids=()):
    excluded_movement_ids=set(excluded_movement_ids)
    agents={a['planet_id']:a for a in payload['agents']};groups=defaultdict(list);result={}
    for m in payload['movements']:
        if m.get('id') in excluded_movement_ids:continue
        wid=agents[m['planet_id']].get('worker_id')
        groups[(wid or m['planet_id'],m['day'])].append(m)
    for group in groups.values():
        if len(group)<2:continue
        ordered=[];error=None
        try:
            for m in group:
                if m['status']!='MATCHED' or not m.get('source_shifts'):raise ValueError
                intervals=[]
                for s in m['source_shifts']:
                    start=datetime.fromisoformat(m['day']+'T'+s['start'])
                    offset=s.get('end_day_offset')
                    if offset is None:offset=int(s['end']<s['start'])
                    end=datetime.fromisoformat(m['day']+'T'+s['end'])+timedelta(days=offset)
                    if end<=start:raise ValueError
                    intervals.append((start,end))
                ordered.append((min(t[0] for t in intervals),max(t[1] for t in intervals),m))
            ordered.sort(key=lambda t:t[0])
            if any(a[1]>b[0] for a,b in zip(ordered,ordered[1:])):raise ValueError
        except (ValueError,KeyError,TypeError):error='Meerdere locaties: volgorde ontbreekt, is overlappend of niet zeker gekoppeld.'
        for index,(start,_,m) in enumerate(ordered if not error else [(None,None,m) for m in group]):
            previous_entry=ordered[index-1] if not error and index else None
            gap=start-previous_entry[1] if previous_entry else None
            previous=previous_entry[2] if previous_entry and gap<=MAX_DIRECT_TRANSFER_GAP else None
            result[(m['planet_id'],m['day'],m['id'])]={'multi_location':True,'error':error,
                'origin_location':previous.get('location') if previous else None,'sequence':index+1,
                'gap_minutes':int(gap.total_seconds()/60) if gap is not None else None,
                'journey_kind':'TRANSFER' if previous else 'HOME'}
    return result
