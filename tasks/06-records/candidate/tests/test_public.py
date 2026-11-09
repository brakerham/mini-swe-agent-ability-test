import unittest
from contactio.csvio import import_contacts, export_contacts

class PublicTests(unittest.TestCase):
    def test_simple_roundtrip(self):
        contacts = [{"id":"1","email":"a@example.invalid","tags":["staff"]}]
        self.assertEqual(import_contacts(export_contacts(contacts)), {"contacts":contacts,"errors":[]})
