"""Read-only analytics derived from the same cached monthly calculations as payroll."""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal('0.01')


def _number(value):
    try:
        return Decimal(str(value)) if value is not None else Decimal('0')
    except Exception:
        return Decimal('0')


def _hours(source):
    """Return source-shift hours while collapsing duplicate export rows."""
    seen = set()
    totals = defaultdict(Decimal)
    for item in source or []:
        key = (item.get('customer') or 'Onbekende klant', item.get('start'), item.get('end'), item.get('end_day_offset'))
        if key in seen:
            continue
        seen.add(key)
        try:
            start = datetime.strptime(item['start'], '%H:%M')
            end = datetime.strptime(item['end'], '%H:%M')
            offset = item.get('end_day_offset')
            if offset is None:
                offset = int(end <= start)
            end += timedelta(days=int(offset))
            duration = Decimal(str(max((end - start).total_seconds(), 0))) / Decimal('3600')
        except (KeyError, TypeError, ValueError):
            duration = Decimal('0')
        totals[key[0]] += duration
    return totals


def _display(value, places=CENT):
    return format(value.quantize(places, rounding=ROUND_HALF_UP), 'f')


def summarize(payloads):
    months = []
    employees_by_month = {}
    customers_by_month = {}
    for payload in sorted(payloads, key=lambda item: item.get('month') or ''):
        month = payload.get('month')
        employee_rows = []
        customer_totals = defaultdict(lambda: {'cost': Decimal('0'), 'kms': Decimal('0'), 'hours': Decimal('0'), 'shifts': Decimal('0')})
        month_cost = month_kms = month_hours = Decimal('0')
        month_shifts = 0
        for employee in payload.get('calculation', {}).get('monthly', {}).get('employees', []):
            cost = kms = hours = Decimal('0')
            paid_shifts = 0
            for shift in employee.get('shifts', []):
                if shift.get('status') != 'CALCULATED' or shift.get('amount') is None:
                    continue
                shift_cost = _number(shift.get('amount'))
                shift_kms = _number(shift.get('reimbursed_kms') if shift.get('reimbursed_kms') is not None else shift.get('distance'))
                customer_hours = _hours(shift.get('source_shifts'))
                shift_hours = sum(customer_hours.values(), Decimal('0'))
                cost += shift_cost; kms += shift_kms; hours += shift_hours; paid_shifts += 1
                if customer_hours:
                    denominator = shift_hours or Decimal(len(customer_hours))
                    for customer, duration in customer_hours.items():
                        weight = (duration if shift_hours else Decimal('1')) / denominator
                        row = customer_totals[customer]
                        row['cost'] += shift_cost * weight
                        row['kms'] += shift_kms * weight
                        row['hours'] += duration
                        row['shifts'] += weight
                else:
                    row = customer_totals['Onbekende klant']
                    row['cost'] += shift_cost; row['kms'] += shift_kms; row['shifts'] += 1
            if paid_shifts:
                employee_rows.append({'worker_id': employee.get('worker_id'), 'name': employee.get('name') or 'Onbekende werknemer',
                    'cost': _display(cost), 'kms': _display(kms), 'hours': _display(hours), 'shifts': paid_shifts,
                    'average_shift_cost': _display(cost / paid_shifts),
                    'average_hour_cost': _display(cost / hours) if hours else None})
                month_cost += cost; month_kms += kms; month_hours += hours; month_shifts += paid_shifts
        employee_rows.sort(key=lambda item: (-Decimal(item['cost']), item['name'].casefold()))
        customer_rows = []
        for customer, row in customer_totals.items():
            customer_rows.append({'customer': customer, 'cost': _display(row['cost']), 'kms': _display(row['kms']),
                'hours': _display(row['hours']), 'shifts': _display(row['shifts']),
                'cost_per_hour': _display(row['cost'] / row['hours']) if row['hours'] else None})
        customer_rows.sort(key=lambda item: (-Decimal(item['cost']), item['customer'].casefold()))
        employee_count = len(employee_rows)
        average_employee_cost = (sum((Decimal(row['cost']) / row['shifts'] for row in employee_rows), Decimal('0')) / employee_count
                                 if employee_count else None)
        average_employee_kms = (sum((Decimal(row['kms']) / row['shifts'] for row in employee_rows), Decimal('0')) / employee_count
                                if employee_count else None)
        months.append({'month': month, 'cost': _display(month_cost), 'kms': _display(month_kms),
            'hours': _display(month_hours), 'shifts': month_shifts, 'employee_count': employee_count,
            'average_shift_cost': _display(month_cost / month_shifts) if month_shifts else None,
            'average_hour_cost': _display(month_cost / month_hours) if month_hours else None,
            'average_employee_cost': _display(average_employee_cost) if average_employee_cost is not None else None,
            'average_employee_kms': _display(average_employee_kms) if average_employee_kms is not None else None})
        employees_by_month[month] = employee_rows
        customers_by_month[month] = customer_rows
    return {'months': months, 'employees_by_month': employees_by_month, 'customers_by_month': customers_by_month,
            'method': 'Kosten en kilometers komen uitsluitend uit berekende shiften. Bij meerdere klanten op één beweging worden ze volgens bronshifturen verdeeld.'}


def build(store):
    with store.connect() as db:
        config = store.matching_config(db)
        rows = db.execute('''SELECT id,payload FROM matching_runs
            WHERE month NOT IN (SELECT month FROM excluded_months)
              AND id IN (SELECT max(id) FROM matching_runs GROUP BY month)
            ORDER BY month''').fetchall()
        # Historical trend rows remain readable after a later month's
        # configuration changes. This is analytics-only: payroll and month
        # review keep their strict stale guard.
        payloads = [store.matching_payload(row, config, db, allow_stale_calculation=True) for row in rows]
    return summarize(payloads)
