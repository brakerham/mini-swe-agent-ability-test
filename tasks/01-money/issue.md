# Invoice totals lose cents and round ties incorrectly

Repair `billing.money` and `billing.invoice` without changing the public API.
`parse_amount(value)` accepts a string, integer, or Decimal, returns a finite,
nonnegative Decimal, and rejects bool, float, invalid text, negative values,
NaN and infinities with ValueError. Whitespace in decimal strings is allowed.
`cents(value)` returns a Decimal quantized to 0.01 using ROUND_HALF_UP.

`invoice(lines, tax_rate="0")` takes iterable mappings with `unit_price` and
`quantity`. Quantity must be an integer >= 0, with bool rejected. Compute each
quantity * unit_price using decimal arithmetic, round each line to cents,
then sum lines. Tax rate has the same accepted scalar types as amounts and
must be in [0, 1]; tax is rounded once from subtotal * rate. Return exactly
{"subtotal": "0.00", "tax": "0.00", "total": "0.00"} (appropriate values).
Never mutate input. Invalid quantities, amounts and rates raise ValueError.
Decimal context in the caller must not alter results for values with at most
20 significant digits, amounts below 10**15, and quantities <= 10**6.
This includes precision, rounding mode, and enabled Inexact/Rounded traps. Empty invoices are valid.

## Submission scope

You may change exactly these implementation files:

- `src/billing/money.py`
- `src/billing/invoice.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
