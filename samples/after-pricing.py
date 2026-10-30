from policy import member_discount


def quote_total(quantity, unit_cents):
    base = quantity * unit_cents
    return base * (100 - member_discount()) // 100
