from app.monthly_aggregation import aggregate


def test_monthly_payroll_reference_enrichment(tmp_path):
    from app.configuration.external_references import append_reference,enrich_monthly
    from app.configuration.routes import RouteStore
    store=RouteStore(tmp_path/'routes.sqlite3')
    with store.transaction() as db:
        worker=store.worker(db,'Alex Voorbeeld')
        append_reference(db,worker,'2026-01-01','00123','Import')
        data={'agents':[{'planet_id':'p1','worker_id':worker}],
              'movements':[{'id':'m1','planet_id':'p1','day':'2026-08-01'}]}
        monthly={'employees':[{'worker_id':worker}]}
        enrich_monthly(db,data,monthly)
    assert monthly['external_references_ready'] is True
    assert monthly['employees'][0]['external_reference']=='00123'


def payload():
    return {'agents':[{'planet_id':'1','worker_id':10,'worker_name':'Agent A','source_names':['A']},
                      {'planet_id':'2','worker_id':20,'worker_name':'Agent B','source_names':['B']}],
            'movements':[{'id':1,'planet_id':'1','day':'2026-08-01','location':'Site'},
                         {'id':2,'planet_id':'1','day':'2026-08-02','location':'Site'},
                         {'id':3,'planet_id':'2','day':'2026-08-03','location':'Other'}]}


def test_employee_totals_keep_details_exclusions_and_hr_amount():
    rows=[{'movement_id':1,'status':'CALCULATED','amount':'4.81','selected_mode':'Auto','distance':'8','rule':'table','amount_source':'BEREKEND'},
          {'movement_id':2,'status':'CALCULATED','amount':'8.25','selected_mode':'Auto','distance':'8','rule':'HR','amount_source':'HR'},
          {'movement_id':3,'status':'EXCLUDED_TELEWORK','amount':None,'selected_mode':'Telework','reason':'Geen vergoeding'}]
    result=aggregate(payload(),rows)
    assert result['calculated_total']=='13.06' and result['employee_count']==2
    assert result['excluded']==1 and result['blocking']==0 and result['ready']
    assert result['employees'][0]['total']=='13.06' and len(result['employees'][0]['shifts'])==2
    assert result['employees'][0]['shifts'][1]['amount_source']=='HR'


def test_blocked_or_later_prevents_month_close():
    rows=[{'movement_id':1,'status':'BLOCKED','amount':None,'reason':'Afstand ontbreekt'},
          {'movement_id':2,'status':'LATER_PHASE','amount':None,'reason':'Controle'},
          {'movement_id':3,'status':'EXCLUDED_TRAIN','amount':None,'reason':'Trein'}]
    result=aggregate(payload(),rows)
    assert not result['ready'] and result['blocking']==2 and result['excluded']==1
    assert sum(not e['ready'] for e in result['employees'])==1


def test_shift_details_keep_calculation_audit_information():
    data=payload()
    data['movements'][0]['source_shifts']=[{'start':'08:00','end':'16:00','customer':'Site klant'}]
    data['movements'][0].update(extra_shift_48h=True,early_late=True)
    row={'movement_id':1,'status':'CALCULATED','amount':'2.22','selected_mode':'Fiets',
         'distance':'3','reimbursed_kms':'6','distance_source':'MAPBOX','distance_valid_from':'2026-01-01',
         'rule':'3 km × 2 × €0.37/km','tariff_kind':'BICYCLE','tariff_id':4,
         'tariff_valid_from':'2026-01-01','tariff_source':'CAO','rate_per_km':'0.37'}

    shift=aggregate(data,[row])['employees'][0]['shifts'][0]

    assert shift['reimbursed_kms']=='6' and shift['distance_source']=='MAPBOX'
    assert shift['tariff_source']=='CAO' and shift['rate_per_km']=='0.37'
    assert shift['extra_shift_48h'] is True and shift['early_late'] is True
    assert shift['source_shifts'][0]['customer']=='Site klant'
