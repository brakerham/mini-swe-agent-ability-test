import json
from pathlib import Path
import unittest
from billing.invoice import invoice

class PublicTests(unittest.TestCase):
    def test_example(self):
        lines = json.loads(Path(__file__).with_name("fixtures.json").read_text())
        self.assertEqual(invoice(lines, "0.1"), {"subtotal":"10.00", "tax":"1.00", "total":"11.00"})
    def test_empty(self):
        self.assertEqual(invoice([])["total"], "0.00")
