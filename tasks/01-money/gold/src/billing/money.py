from decimal import Decimal, InvalidOperation, localcontext, Context, ROUND_HALF_UP

def parse_amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("amount must be a decimal string, integer or Decimal")
    try:
        result = Decimal(value.strip() if isinstance(value, str) else value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid amount") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("amount must be finite and nonnegative")
    return result

def cents(value):
    with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)) as context:
        context.prec = 64
        return parse_amount(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
