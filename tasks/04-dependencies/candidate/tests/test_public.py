import unittest
from buildplan.planner import plan

class PublicTests(unittest.TestCase):
    def test_chain(self):
        self.assertEqual(plan({"app":["lib"],"lib":[]}), ["lib","app"])
    def test_empty(self):
        self.assertEqual(plan({}), [])
