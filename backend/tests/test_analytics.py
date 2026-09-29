from app.analytics import summarize


def payload(month='2026-08'):
    return {'month': month, 'calculation': {'monthly': {'employees': [
        {'worker_id': 1, 'name': 'Agent Een', 'shifts': [
            {'status': 'CALCULATED', 'amount': '12.00', 'distance': '10', 'reimbursed_kms': None,
             'source_shifts': [{'customer': 'Klant A', 'start': '08:00', 'end': '12:00', 'end_day_offset': 0},
                               {'customer': 'Klant B', 'start': '12:00', 'end': '16:00', 'end_day_offset': 0}]},
            {'status': 'EXCLUDED_TRAIN', 'amount': None, 'distance': None, 'source_shifts': []},
            {'status': 'CALCULATED', 'amount': '8.00', 'distance': '4', 'reimbursed_kms': '8',
             'source_shifts': [{'customer': 'Klant A', 'start': '22:00', 'end': '06:00', 'end_day_offset': 1},
                               {'customer': 'Klant A', 'start': '22:00', 'end': '06:00', 'end_day_offset': 1}]}]},
        {'worker_id': 2, 'name': 'Agent Twee', 'shifts': [
            {'status': 'CALCULATED', 'amount': '4.00', 'distance': '2', 'source_shifts': []}]}
    ]}}}


def test_analytics_totals_averages_and_customer_allocation():
    result = summarize([payload()])
    month = result['months'][0]
    assert month == {'month': '2026-08', 'cost': '24.00', 'kms': '20.00', 'hours': '16.00', 'shifts': 3,
                     'employee_count': 2, 'average_shift_cost': '8.00', 'average_hour_cost': '1.50',
                     'average_employee_cost': '7.00', 'average_employee_kms': '5.50'}
    assert [row['name'] for row in result['employees_by_month']['2026-08']] == ['Agent Een', 'Agent Twee']
    customers = {row['customer']: row for row in result['customers_by_month']['2026-08']}
    assert customers['Klant A']['cost'] == '14.00'
    assert customers['Klant A']['kms'] == '13.00'
    assert customers['Klant A']['hours'] == '12.00'
    assert customers['Klant B']['cost'] == '6.00'
    assert customers['Onbekende klant']['cost'] == '4.00'


def test_analytics_keeps_months_separate():
    result = summarize([payload('2026-09'), payload('2026-08')])
    assert [row['month'] for row in result['months']] == ['2026-08', '2026-09']
    assert set(result['employees_by_month']) == {'2026-08', '2026-09'}
