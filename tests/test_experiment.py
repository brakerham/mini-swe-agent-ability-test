"""Offline orchestration checks: fixture HTTP/model and Docker are never called."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from benchmark import core, experiment


class ExperimentTests(unittest.TestCase):
    def run_fixture(self, *, worker_status="completed", worker_timed_out=False,
                    worker_code=0, repetitions=1, fail_start=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "experiment"
        commands = []
        task = core.task_list()[0]
        image = "sha256:" + "f" * 64
        args = SimpleNamespace(allow_paid=True, config=str(core.ROOT / "configs/deepseek-v4-pro.json"),
            repetitions=repetitions, output=str(output), image="unresolved-tag", task=task["id"])

        def execute(argv, **kwargs):
            commands.append((argv, kwargs))
            record = {"returncode": 0, "timed_out": False, "stdout": "", "stderr": ""}
            if argv[:2] == ["docker", "create"]:
                return {**record, "stdout": "a" * 64}
            if argv[:2] == ["docker", "start"] and fail_start:
                return {**record, "returncode": 1, "stderr": "fixture start failure"}
            if argv[:2] == ["git", "rev-parse"]:
                return {**record, "stdout": "b" * 40}
            if "benchmark.worker" in argv:
                payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
                # Credentials are inherited by the host worker only, never its payload.
                self.assertNotIn("fixture-deepseek-key", json.dumps(payload))
                self.assertEqual(kwargs["env"]["DEEPSEEK_API_KEY"], "fixture-deepseek-key")
                self.assertNotIn("UNRELATED_PRIVATE_TOKEN", kwargs["env"])
                core.write_json(payload["result_path"], {"status": worker_status,
                    "steps": 1, "cost_usd": None, "usage": {"total_tokens": 30}})
                return {**record, "returncode": worker_code, "timed_out": worker_timed_out,
                        "stdout": "log fixture-deepseek-key", "stderr": "fixture-deepseek-key"}
            return record

        grade_result = {"status": "resolved", "resolved": True, "partial_score": 1.0,
                        "submission": {"patch": "fixture patch", "valid": True}}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-deepseek-key",
                "UNRELATED_PRIVATE_TOKEN": "fixture-unrelated"}), \
             mock.patch.object(experiment.importlib.metadata, "version", return_value="2.4.6"), \
             mock.patch.object(experiment.importlib.metadata, "distributions", return_value=[]), \
             mock.patch.object(experiment, "docker_image", return_value={"id": image}), \
             mock.patch.object(experiment, "execute", side_effect=execute), \
             mock.patch.object(experiment.environment, "execute", side_effect=execute), \
             mock.patch.object(experiment, "grade", side_effect=lambda *a, **kw: {
                 **grade_result, "submission": dict(grade_result["submission"])}):
            self.assertEqual(experiment.run_experiment(args), output)
        plan = core.read_json(output / "plan.json")
        results = [core.read_json(output / item["directory"] / "result.json") for item in plan["attempts"]]
        for path in output.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"fixture-deepseek-key", path.read_bytes())
        return output, plan, results, commands

    def test_completed_agent_and_passing_grade_resolves(self):
        output, plan, results, commands = self.run_fixture()
        self.assertEqual(len(plan["attempts"]), 1)
        self.assertEqual(results[0]["status"], "resolved")
        self.assertTrue(results[0]["resolved"])
        self.assertTrue(results[0]["functional_resolved"])
        self.assertEqual(core.report(output)["resolved_rate"], 1)
        create = next(argv for argv, _ in commands if argv[:2] == ["docker", "create"])
        self.assertIn("sha256:" + "f" * 64, create)
        self.assertNotIn("unresolved-tag", create)
        self.assertIn("--read-only", create)
        self.assertEqual(create[create.index("--network") + 1], "none")
        self.assertTrue(any(argv[:4] == ["docker", "rm", "-f", "-v"] for argv, _ in commands))

    def test_timeout_or_agent_error_never_counts_as_completed_resolution(self):
        scenarios = [dict(worker_timed_out=True, worker_code=-1),
                     dict(worker_status="agent_error"), dict(worker_code=1)]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                output, _, results, commands = self.run_fixture(**scenario)
                self.assertFalse(results[0]["resolved"])
                self.assertEqual(results[0]["partial_score"], 0)
                self.assertTrue(results[0]["functional_resolved"])
                self.assertEqual(core.report(output)["resolved_rate"], 0)
                self.assertTrue(any(argv[:4] == ["docker", "rm", "-f", "-v"] for argv, _ in commands))

    def test_container_start_failure_retains_attempt_and_cleanup(self):
        output, plan, results, commands = self.run_fixture(fail_start=True, repetitions=2)
        self.assertEqual(len(plan["attempts"]), 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(core.report(output)["planned"], 2)
        self.assertTrue(all(item["status"] == "infra_error" for item in results))
        cleanup_calls = [argv for argv, _ in commands if argv[:4] == ["docker", "rm", "-f", "-v"]]
        self.assertEqual(len(cleanup_calls), 2)


if __name__ == "__main__":
    unittest.main()
