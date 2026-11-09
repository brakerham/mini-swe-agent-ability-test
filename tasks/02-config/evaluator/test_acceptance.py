import copy
import unittest
from configkit.loader import load_config
from configkit.merge import deep_merge

class RegressionTests(unittest.TestCase):
    def test_flat_and_literal(self):
        self.assertEqual(load_config({"port":80,"label":"hello"},{"port":443},{}), {"port":443,"label":"hello"})
    def test_top_level_environment(self):
        self.assertEqual(load_config({"host":"${HOST}"},{},{"HOST":"localhost"}), {"host":"localhost"})

class FeatureTests(unittest.TestCase):
    def test_nested_override_preserves_siblings(self):
        self.assertEqual(deep_merge({"db":{"host":"old","port":5432}},{"db":{"host":"new"}}), {"db":{"host":"new","port":5432}})
    def test_no_container_aliases(self):
        base = {"keep":{"a":[1]}}
        override = {"replace":[{"b":2}]}
        result = deep_merge(base, override)
        result["keep"]["a"].append(3)
        result["replace"][0]["b"] = 4
        self.assertEqual(base, {"keep":{"a":[1]}})
        self.assertEqual(override, {"replace":[{"b":2}]})
    def test_recursive_expansion(self):
        data = {"services":[{"url":"${URL}","names":["${NAME}","ok"]}]}
        self.assertEqual(load_config(data, {}, {"URL":"https://example.invalid", "NAME":""}), {"services":[{"url":"https://example.invalid","names":["","ok"]}]})
    def test_missing_nested_variable(self):
        with self.assertRaises(KeyError): load_config({"a":[{"x":"${ABSENT}"}]},{},{})
    def test_only_exact_valid_placeholders(self):
        literals = ["${BAD-NAME}","${}","${1BAD}","prefix${A}","${A}suffix", "${A}\n"]
        for text in literals:
            with self.subTest(text=text): self.assertEqual(load_config({"x":text},{},{}), {"x":text})
    def test_expansion_happens_after_merge(self):
        base = {"db":{"removed":"${MISSING}","keep":"${A}"}}
        override = {"db":{"removed":None,"flags":[1]}}
        original = copy.deepcopy((base, override))
        self.assertEqual(load_config(base, override, {"A":"${B}"}), {"db":{"removed":None,"keep":"${B}","flags":[1]}})
        self.assertEqual((base, override), original)
