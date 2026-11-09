from decimal import Decimal, localcontext, Context, ROUND_HALF_UP
from .money import cents, parse_amount

def invoice(lines, tax_rate="0"):
    rate = parse_amount(tax_rate)
    if rate > 1:
        raise ValueError("tax rate must be in [0, 1]")
    with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)) as context:
        context.prec = 64
        subtotal = Decimal("0.00")
        for line in lines:
            quantity = line["quantity"]
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                raise ValueError("quantity must be a nonnegative integer")
            subtotal += cents(parse_amount(line["unit_price"]) * quantity)
        tax = cents(subtotal * rate)
        return {"subtotal": f"{subtotal:.2f}", "tax": f"{tax:.2f}", "total": f"{subtotal + tax:.2f}"}
