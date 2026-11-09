import unittest
from ttlcache.cache import Cache

class PublicTests(unittest.TestCase):
    def test_roundtrip(self):
        cache = Cache(2,10,lambda:0)
        cache.set("a",1)
        self.assertEqual(cache.get("a"),1)
        self.assertIsNone(cache.get("missing"))
    def test_fifo_is_lru_without_reads(self):
        cache = Cache(1,10,lambda:0)
        cache.set("a",1)
        cache.set("b",2)
        self.assertEqual(cache.keys(),["b"])
