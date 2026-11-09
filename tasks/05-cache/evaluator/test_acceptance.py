import unittest
from ttlcache.cache import Cache

class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now

class RegressionTests(unittest.TestCase):
    def test_value_identity_and_none(self):
        cache = Cache(2,10,lambda:0)
        value = []
        cache.set("a",value)
        cache.set("b",None)
        self.assertIs(cache.get("a"),value)
        self.assertIsNone(cache.get("b","missing"))
    def test_missing_default(self):
        self.assertEqual(Cache(1,1,lambda:0).get("absent",42),42)

class FeatureTests(unittest.TestCase):
    def test_get_updates_recency(self):
        cache = Cache(2,10,lambda:0)
        cache.set("a",1); cache.set("b",2); cache.get("a"); cache.set("c",3)
        self.assertEqual(cache.keys(),["a","c"])
    def test_update_resets_ttl_and_recency(self):
        clock = Clock(); cache = Cache(2,10,clock)
        cache.set("a",1); cache.set("b",2)
        clock.now = 5; cache.set("a",3); cache.set("c",4)
        self.assertEqual(cache.keys(),["a","c"])
        clock.now = 10; self.assertEqual(cache.get("a"),3)
        clock.now = 15; self.assertIsNone(cache.get("a"))
    def test_expiration_boundary(self):
        clock = Clock(); cache = Cache(1,10,clock); cache.set("a",1)
        clock.now = 10
        self.assertEqual(cache.get("a","expired"),"expired")
    def test_reads_do_not_extend_ttl(self):
        clock = Clock(); cache = Cache(1,10,clock); cache.set("a",1)
        clock.now = 9; self.assertEqual(cache.get("a"),1)
        clock.now = 10; self.assertEqual(cache.keys(),[])
    def test_expired_entries_do_not_evict_live(self):
        clock = Clock(); cache = Cache(2,10,clock); cache.set("a",1)
        clock.now = 5; cache.set("b",2)
        clock.now = 6; cache.set("a",3)
        clock.now = 15; cache.set("c",4)
        self.assertEqual(cache.keys(),["a","c"])
    def test_zero_ttl(self):
        cache = Cache(1,0,lambda:0); cache.set("a",1)
        self.assertEqual(cache.keys(),[])
    def test_constructor_validation(self):
        for capacity in [0,-1,True,1.5,"2"]:
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError): Cache(capacity,1,lambda:0)
        for ttl in [-1,True,float("nan"),float("inf"),"1"]:
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError): Cache(1,ttl,lambda:0)
