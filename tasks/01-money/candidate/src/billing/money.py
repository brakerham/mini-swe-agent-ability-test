from decimal import Decimal

def parse_amount(value):
    return Decimal(str(value))

def cents(value):
    return Decimal(str(round(float(value), 2)))
