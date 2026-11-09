import copy
import random
import unittest
from buildplan.graph import validate
from buildplan.planner import plan

class RegressionTests(unittest.TestCase):
    def test_chain(self):
        self.assertEqual(plan({"app":["lib"],"lib":["core"],"core":[]}), ["core","lib","app"])
    def test_empty(self):
        self.assertEqual(plan({}), [])

class FeatureTests(unittest.TestCase):
    def test_insertion_order_among_ready(self):
        self.assertEqual(plan({"z":[],"a":[],"b":["z"]}), ["z","a","b"])
    def test_newly_ready_earlier_node(self):
        self.assertEqual(plan({"x":["z"],"z":[],"a":[]}), ["z","x","a"])
    def test_cycles(self):
        for graph in [{"a":["a"]},{"a":["b"],"b":["a"]},{"ok":[],"a":["b"],"b":["a"]}]:
            with self.subTest(graph=graph):
                with self.assertRaisesRegex(ValueError,"cycle"): plan(graph)
    def test_missing_dependency(self):
        with self.assertRaisesRegex(ValueError,"missing_lib"): plan({"app":["missing_lib"]})
    def test_validate_types(self):
        for graph in [{1:[]},{"a":"a"},{"a":[1]},[],{"a":("b",),"b":[]}]:
            with self.subTest(graph=graph):
                with self.assertRaises(ValueError): validate(graph)
    def test_duplicate_edges_no_mutation(self):
        graph = {"z":[],"b":["z","z"],"a":[]}
        original = copy.deepcopy(graph)
        self.assertEqual(plan(graph), ["z","b","a"])
        self.assertEqual(graph, original)
    def test_seeded_dags_stable_reference(self):
        rng = random.Random(90210)
        for _ in range(20):
            names = [f"n{i}" for i in range(8)]
            shuffled = names[:]
            rng.shuffle(shuffled)
            graph = {name:[prior for prior in names[:names.index(name)] if rng.random()<.3] for name in shuffled}
            completed, expected = set(), []
            while len(completed)<len(graph):
                ready = next(name for name in graph if name not in completed and all(dep in completed for dep in graph[name]))
                completed.add(ready)
                expected.append(ready)
            self.assertEqual(plan(graph), expected)
