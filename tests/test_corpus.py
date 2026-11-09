"""Offline calibration: public baseline passes, each feature fails, gold passes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"

def run_tests(candidate, evaluator=None, test_class=None):
    env = {**os.environ, "PYTHONPATH":str(candidate / "src"), "PYTHONDONTWRITEBYTECODE":"1"}
    if evaluator is None:
        command = [sys.executable,"-m","unittest","discover","-s","tests","-v"]
    else:
        env["PYTHONPATH"] += os.pathsep + str(evaluator)
        command = [sys.executable,"-m","unittest",f"test_acceptance.{test_class}" if test_class else "test_acceptance", "-v"]
    return subprocess.run(command,cwd=candidate,env=env,capture_output=True,text=True,timeout=20)

class CorpusTests(unittest.TestCase):
    def test_manifest_and_layout(self):
        manifest = json.loads((TASKS/"manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"],1)
        self.assertEqual(len(manifest["tasks"]),6)
        self.assertEqual(len({task["id"] for task in manifest["tasks"]}),6)
        for task in manifest["tasks"]:
            with self.subTest(task=task["id"]):
                base = TASKS/task["id"]
                self.assertTrue((base/"issue.md").is_file())
                self.assertTrue((base/"evaluator/test_acceptance.py").is_file())
                self.assertFalse((base/"candidate/gold").exists())
                self.assertFalse((base/"candidate/evaluator").exists())
                self.assertEqual({path.relative_to(base/"gold").as_posix() for path in (base/"gold").rglob("*.py")}, set(task["allowed_paths"]))

    def test_all_public_baselines_pass(self):
        for base in sorted(TASKS.glob("[0-9][0-9]-*")):
            with self.subTest(task=base.name):
                result = run_tests(base/"candidate")
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_all_regression_baselines_pass(self):
        for base in sorted(TASKS.glob("[0-9][0-9]-*")):
            with self.subTest(task=base.name):
                result = run_tests(base/"candidate",base/"evaluator","RegressionTests")
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_each_baseline_feature_method_fails(self):
        # Fail-to-pass labels are calibrated per method, not merely per suite.
        import ast
        for base in sorted(TASKS.glob("[0-9][0-9]-*")):
            tree = ast.parse((base/"evaluator/test_acceptance.py").read_text(encoding="utf-8"))
            methods = [item.name for node in tree.body if isinstance(node,ast.ClassDef) and node.name == "FeatureTests" for item in node.body if isinstance(item,ast.FunctionDef) and item.name.startswith("test_")]
            self.assertGreaterEqual(len(methods),6)
            for method in methods:
                with self.subTest(task=base.name,method=method):
                    result = run_tests(base/"candidate",base/"evaluator",f"FeatureTests.{method}")
                    self.assertNotEqual(result.returncode,0,"baseline unexpectedly passed: " + method)
                    self.assertNotIn("ImportError", result.stderr, "baseline failure must not be an import failure: " + result.stderr)

    def test_all_gold_public_and_acceptance_pass(self):
        for base in sorted(TASKS.glob("[0-9][0-9]-*")):
            with self.subTest(task=base.name), tempfile.TemporaryDirectory() as temporary:
                candidate = Path(temporary)/"candidate"
                shutil.copytree(base/"candidate",candidate)
                shutil.copytree(base/"gold",candidate,dirs_exist_ok=True)
                for evaluator in [None,base/"evaluator"]:
                    result = run_tests(candidate,evaluator)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
