import copy
from decimal import Decimal, localcontext, Inexact, Rounded, ROUND_DOWN
import unittest
from billing.invoice import invoice
from billing.money import cents, parse_amount

class RegressionTests(unittest.TestCase):
    def test_integer_invoice(self):
        self.assertEqual(invoice([{"unit_price":"5", "quantity":2}], "0.1"), {"subtotal":"10.00","tax":"1.00","total":"11.00"})
    def test_input_unchanged(self):
        rows = [{"unit_price":"2", "quantity":3}]
        original = copy.deepcopy(rows)
        invoice(iter(rows))
        self.assertEqual(rows, original)

class FeatureTests(unittest.TestCase):
    def test_half_up(self):
        for value, expected in [("1.005","1.01"),("2.675","2.68"),("0.005","0.01"),("100.015","100.02")]:
            with self.subTest(value=value):
                self.assertEqual(cents(value), Decimal(expected))
    def test_round_each_line(self):
        self.assertEqual(invoice([{"unit_price":"0.005","quantity":1}] * 3, "0.5"), {"subtotal":"0.03","tax":"0.02","total":"0.05"})
    def test_reject_nonfinite_and_negative(self):
        for value in ["-0.01", "NaN", "Infinity", "-Infinity", "bad", True, 1.2]:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError): parse_amount(value)
    def test_quantity_validation(self):
        for quantity in [-1, 1.5, True, "2", None]:
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError): invoice([{"unit_price":"1", "quantity":quantity}])
    def test_rate_validation(self):
        for rate in ["1.01", "-0.01", "NaN", True]:
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError): invoice([], rate)
    def test_context_independence(self):
        with localcontext() as context:
            context.prec = 5
            context.rounding = ROUND_DOWN
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.assertEqual(invoice([{"unit_price":Decimal("123456789012345.55555"),"quantity":3}], "0.075"), {"subtotal":"370370367037036.67","tax":"27777777527777.75","total":"398148144564814.42"})
