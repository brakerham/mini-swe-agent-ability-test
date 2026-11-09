import sqlite3
import unittest
from eventlog.store import page

class PublicTests(unittest.TestCase):
    def test_small_page(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE events(id INTEGER PRIMARY KEY,timestamp INTEGER,kind TEXT,payload TEXT)")
            db.execute("INSERT INTO events VALUES(1,10,'a','hello')")
            self.assertEqual(page(db)["items"], [{"id":1,"timestamp":10,"kind":"a","payload":"hello"}])
            self.assertIsNone(page(db)["next_cursor"])
