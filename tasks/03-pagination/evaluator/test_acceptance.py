import base64
import json
import sqlite3
import unittest
from eventlog.store import page
from eventlog.cursor import encode, decode

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE events(id INTEGER PRIMARY KEY,timestamp INTEGER NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL)")
        self.db.executemany("INSERT INTO events VALUES(?,?,?,?)", [(10,1,"a","one"),(20,1,"b","two"),(30,1,"a","three"),(40,2,"a","four")])

class RegressionTests(DatabaseTests):
    def test_small_result_filter(self):
        self.assertEqual([row["id"] for row in page(self.db, kind="b")["items"]], [20])
    def test_empty(self):
        self.assertEqual(page(self.db, kind="absent"), {"items":[],"next_cursor":None})

class FeatureTests(DatabaseTests):
    def test_exact_final_page(self):
        self.assertIsNone(page(self.db, limit=4)["next_cursor"])
    def test_equal_timestamps_nonsequential_ids(self):
        first = page(self.db, limit=2)
        self.assertEqual(decode(first["next_cursor"], None), (1,20))
        second = page(self.db, limit=2, cursor=first["next_cursor"])
        self.assertEqual([row["id"] for row in second["items"]], [30,40])
        self.assertIsNone(second["next_cursor"])
    def test_insert_before_cursor(self):
        first = page(self.db, limit=2)
        self.db.execute("INSERT INTO events VALUES(5,0,'a','late insert')")
        second = page(self.db, limit=2, cursor=first["next_cursor"])
        self.assertEqual([row["id"] for row in second["items"]], [30,40])
    def test_filter_bound_to_cursor(self):
        cursor = page(self.db, limit=1, kind="a")["next_cursor"]
        with self.assertRaises(ValueError): page(self.db, cursor=cursor, kind="b")
    def test_invalid_limits(self):
        for limit in [0,-1,101,True,1.5,"2",None]:
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError): page(self.db, limit=limit)
    def test_cursor_validation(self):
        def token(data): return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        good = {"v":1,"t":1,"id":2,"kind":None}
        invalid = ["!bad!", "x"*2049, token([]), token({**good,"v":2}), token({**good,"v":True}), token({**good,"id":True}), token({**good,"id":0}), token({**good,"t":"1"}), token({**good,"extra":0}), token({"v":1,"t":1,"id":2})]
        invalid.extend([token({**good,"t":2**63}), token({**good,"id":2**63}), token({**good,"kind":"k"*129}), base64.urlsafe_b64encode(b'{"v":1,"v":1,"t":1,"id":2,"kind":null}').decode()])
        for value in invalid:
            with self.subTest(value=value[:80]):
                with self.assertRaises(ValueError): decode(value, None)
    def test_negative_timestamp_and_row_factory(self):
        self.db.row_factory = sqlite3.Row
        original = self.db.row_factory
        cursor = encode(-2, 10, None)
        self.assertEqual(decode(cursor, None), (-2,10))
        self.assertEqual(len(page(self.db,cursor=cursor)["items"]),4)
        self.assertIs(self.db.row_factory, original)
        for arguments in [(True,1,None), (2**63,1,None), (0,2**63,None), (0,1,"x"*129)]:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError): encode(*arguments)
        with self.assertRaises(ValueError): page(self.db, kind=True)
