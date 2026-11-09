import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import core
from benchmark.__main__ import main


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.candidate = Path(self.temp.name) / "candidate"
        self.task = core.task_list()[0]
        core.prepare(self.task, self.candidate)

    def test_prepared_task_has_no_evaluator_or_gold(self):
        files = core.inventory(self.candidate)
        self.assertIn("ISSUE.md", files)
        self.assertFalse(any("gold/" in name or "evaluator/" in name for name in files))

    def test_source_and_authored_tests_allowed_but_protected_change_rejected(self):
        (self.candidate / "tests" / "test_agent.py").write_text("# agent evidence\n")
        self.assertTrue(core.submission(self.task, self.candidate)["valid"])
        (self.candidate / "ISSUE.md").write_text("tampered")
        self.assertFalse(core.submission(self.task, self.candidate)["valid"])

    def test_deleted_source_rejected(self):
        (self.candidate / self.task["allowed_paths"][0]).unlink()
        result = core.submission(self.task, self.candidate)
        self.assertFalse(result["valid"])
        self.assertTrue(any("deleted" in item for item in result["violations"]))

    def test_unexpected_module_rejected(self):
        (self.candidate / "src" / "unittest.py").write_text("raise SystemExit(0)")
        self.assertEqual(core.grade(self.task, self.candidate)["status"], "invalid_submission")

    def test_no_overwrite(self):
        with self.assertRaises(ValueError):
            core.prepare(self.task, self.candidate)

    def test_symlink_rejected_when_supported(self):
        target = Path(self.temp.name) / "outside.py"
        target.write_text("pass")
        try:
            (self.candidate / "tests" / "link.py").symlink_to(target)
        except OSError:
            self.skipTest("OS does not allow symlink creation")
        with self.assertRaises(ValueError):
            core.inventory(self.candidate)

    def test_test_tampering_never_replaces_trusted_tests(self):
        for test in (self.candidate / "tests").glob("test*.py"):
            test.write_text("raise AssertionError('candidate test must not execute')")
        result = core.grade(self.task, self.candidate)
        self.assertEqual(result["suites"]["public"]["status"], "passed")
        self.assertFalse(result["resolved"])


class ParserTests(unittest.TestCase):
    def fake(self, text, returncode=0):
        return {"stdout": text, "stderr": "", "returncode": returncode, "timed_out": False}

    def check(self, payload, expected=None, returncode=0):
        record = "BENCHMARK_RESULT=" + json.dumps(payload)
        with patch.object(core, "execute", return_value=self.fake(record, returncode)), \
             patch.object(core, "expected_tests", return_value=expected or ["t.C.test_one"]):
            return core.run_suite(core.task_list()[0], Path.cwd(), "FeatureTests")

    def test_zero_tests_cannot_pass(self):
        result = self.check({"tests_run": 0, "events": [], "successful": True})
        self.assertEqual(result["status"], "invalid_result")

    def test_skip_cannot_pass(self):
        result = self.check({"tests_run": 1, "events": [{"id": "t.C.test_one", "status": "skipped"}], "successful": True})
        self.assertEqual(result["status"], "failed")

    def test_duplicate_record_cannot_pass(self):
        with patch.object(core, "execute", return_value=self.fake("BENCHMARK_RESULT={}\nBENCHMARK_RESULT={}")):
            result = core.run_suite(core.task_list()[0], Path.cwd(), "FeatureTests")
        self.assertEqual(result["status"], "invalid_result")

    def test_subtest_failure_counts_as_feature_failure(self):
        result = self.check({"tests_run": 1, "events": [{"id": "t.C.test_one", "status": "failed_subtest"}], "successful": False}, returncode=1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed"], 0)

    def test_incomplete_ids_rejected(self):
        result = self.check({"tests_run": 1, "events": [{"id": "t.C.test_wrong", "status": "passed"}], "successful": True})
        self.assertEqual(result["status"], "invalid_result")


class ReportingTests(unittest.TestCase):
    def test_missing_attempts_remain_in_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            task_id = core.task_list()[0]["id"]
            core.write_json(folder / "plan.json", {"attempts": [
                {"task_id": task_id, "repetition": 1, "directory": "first"},
                {"task_id": task_id, "repetition": 2, "directory": "missing"}]})
            core.write_json(folder / "first" / "result.json", {"status": "resolved", "resolved": True, "partial_score": 1})
            result = core.report(folder)
            self.assertEqual(result["planned"], 2)
            self.assertEqual(result["resolved_rate"], 0.5)
            self.assertEqual(result["status_counts"]["missing"], 1)
            self.assertIsNone(result["known_cost_usd"])

    def test_run_requires_explicit_paid_flag_before_any_dependencies(self):
        self.assertEqual(main(["run", "--output", "runs/never-created"]), 2)
        self.assertFalse((core.ROOT / "runs" / "never-created").exists())


if __name__ == "__main__":
    unittest.main()
