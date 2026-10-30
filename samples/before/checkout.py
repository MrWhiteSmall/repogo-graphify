from pricing import quote_total
from storage import save_order


def place_order(order_id, quantity, unit_cents):
    total = quote_total(quantity, unit_cents)
    return save_order(order_id, total)
