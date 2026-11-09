from .money import cents, parse_amount

def invoice(lines, tax_rate="0"):
    subtotal = sum(float(line["unit_price"]) * line["quantity"] for line in lines)
    tax = cents(subtotal * float(tax_rate))
    return {"subtotal": f"{subtotal:.2f}", "tax": f"{tax:.2f}", "total": f"{subtotal + float(tax):.2f}"}
