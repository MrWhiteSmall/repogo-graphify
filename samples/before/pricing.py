from policy import standard_discount


def quote_total(quantity, unit_cents):
    base = quantity * unit_cents
    return base * (100 - standard_discount()) // 100
