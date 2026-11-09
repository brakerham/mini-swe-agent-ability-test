import copy
import unittest
from contactio.csvio import import_contacts, export_contacts
from contactio.normalize import normalize_contact

class RegressionTests(unittest.TestCase):
    def test_simple_record(self):
        self.assertEqual(import_contacts("id,email,tags\n1,a@example.invalid,staff\n"), {"contacts":[{"id":"1","email":"a@example.invalid","tags":["staff"]}],"errors":[]})
    def test_export_simple(self):
        self.assertEqual(export_contacts([{"id":"1","email":"a@b","tags":[]}]), "id,email,tags\n1,a@b,\n")

class FeatureTests(unittest.TestCase):
    def test_bom_headers_and_normalization(self):
        result = import_contacts("\ufeff ID , EMAIL , tags ,ignored\n 1 , A@EXAMPLE.INVALID , x ; x ; y ; ,extra\n")
        self.assertEqual(result,{"contacts":[{"id":"1","email":"a@example.invalid","tags":["x","y"]}],"errors":[]})
    def test_csv_quoting_and_roundtrip(self):
        contacts = [{"id":"person,one\nsecond line","email":"a@b","tags":["a,b","c\nd"]}]
        self.assertEqual(import_contacts(export_contacts(contacts)), {"contacts":contacts,"errors":[]})
        self.assertNotIn("\r\n",export_contacts(contacts))
    def test_row_errors_priority_and_duplicate(self):
        text = "id,email,tags\nx,bad,\nx,a@b,ok\nx,c@d,ignored\n ,bad,\ny,z@q,too,many\nz,z @q,\n"
        result = import_contacts(text)
        self.assertEqual(result["contacts"],[{"id":"x","email":"a@b","tags":["ok"]}])
        self.assertEqual(result["errors"],[{"row":2,"reason":"email"},{"row":4,"reason":"duplicate"},{"row":5,"reason":"id"},{"row":6,"reason":"columns"},{"row":7,"reason":"email"}])
    def test_logical_record_numbers_and_blank_lines(self):
        text = 'id,email\n"one\ntwo",a@b\n\nmissing,bad\n'
        self.assertEqual(import_contacts(text), {"contacts":[{"id":"one\ntwo","email":"a@b","tags":[]}],"errors":[{"row":3,"reason":"email"}]})
    def test_invalid_headers_and_quoting(self):
        for text in ["", "\ufeff\ufeffid,email\n1,a@b\n", "id\n1\n", "email\na@b\n", "id,email, ID \n1,a@b,2\n", 'id,email\n"unclosed,a@b\n']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError): import_contacts(text)
    def test_email_validation_and_input_immutable(self):
        for email in ["", "@b", "a@", "a@@b", "a b@c", "a@b\tc"]:
            with self.subTest(email=email):
                with self.assertRaisesRegex(ValueError,"email"): normalize_contact({"id":"x","email":email})
        row = {"id":" X ","email":" A@B ","tags":" a ;a;b "}
        original = copy.deepcopy(row)
        self.assertEqual(normalize_contact(row), {"id":"X","email":"a@b","tags":["a","b"]})
        self.assertEqual(row, original)
    def test_missing_cells_and_optional_tags(self):
        self.assertEqual(import_contacts("id,email\na,a@b\nb\n"), {"contacts":[{"id":"a","email":"a@b","tags":[]}],"errors":[{"row":3,"reason":"columns"}]})
