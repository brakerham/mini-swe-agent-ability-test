import unittest
from configkit.loader import load_config
from configkit.merge import deep_merge

class PublicTests(unittest.TestCase):
    def test_flat_override(self):
        self.assertEqual(deep_merge({"port":80},{"port":443}), {"port":443})
    def test_top_level_environment(self):
        self.assertEqual(load_config({"host":"${HOST}"},{},{"HOST":"local"}), {"host":"local"})
