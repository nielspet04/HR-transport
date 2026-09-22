"""Reconcile retained Planet evidence and profiles; never suppress unknown agents."""
def check(db,payload):
    agents={a['planet_id']:a for a in payload['agents']}
    movements=payload['movements'];issues=[]
    manifest=payload.get('source_manifest')
    if manifest is None:
        issues.append({'reason':'Broncontrole ontbreekt in deze oudere verwerking. Klik op Vernieuwen.','planet_id':None})
    else:
        actual={s['row'] for m in movements for s in m.get('source_shifts',[])}
        expected={s['row'] for s in manifest}
        for pid in sorted({s['planet_id'] for s in manifest}):
            if pid not in agents:issues.append({'planet_id':pid,'reason':'Agent uit de bron ontbreekt in het maandsoverzicht.'})
        missing=sorted(expected-actual)
        if missing:issues.append({'planet_id':None,'reason':'Bronshiften ontbreken in het maandsoverzicht.','source_rows':missing})
    homes=[dict(r) for r in db.execute('SELECT worker_id,valid_from FROM worker_addresses')]
    workers={r['id'] for r in db.execute('SELECT id FROM workers')}
    for pid,agent in agents.items():
        wid=agent.get('worker_id');own=[m for m in movements if m['planet_id']==pid]
        if wid not in workers:
            issues.append({'planet_id':pid,'name':agent.get('worker_name') or ' / '.join(agent.get('source_names',[])),
                           'reason':'Geen zeker gekoppeld werknemersprofiel. Bevestig de koppeling of maak de werknemer aan.','movements':len(own)})
        else:
            missing=[m for m in own if not any(h['worker_id']==wid and h['valid_from']<=m['day'] for h in homes)]
            if missing:issues.append({'planet_id':pid,'name':agent.get('worker_name'),
                                     'reason':'Woonadres ontbreekt of is niet geldig op de shiftdatum.','movements':len(missing)})
    return {'issues':issues,'complete':not issues,'agents':len(agents),'movements':len(movements),
            'source_checked':manifest is not None}
