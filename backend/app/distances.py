"""Operational kilometers: always ceil; retain provider precision separately."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING


def whole_kms(value):
    try:
        if value is None or isinstance(value,bool):raise ValueError
        km=Decimal(str(value).replace(',','.'))
        if not km.is_finite() or km<0:raise ValueError
        return int(km.to_integral_value(rounding=ROUND_CEILING))
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError('Ongeldige afstand.') from None


def display_route(row):
    result=dict(row)
    if result.get('kms') is not None:result['kms']=str(whole_kms(result['kms']))
    return result
