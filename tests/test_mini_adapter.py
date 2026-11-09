"""Zero-cost checks. Optional real-library tests skip without requirements-agent."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from benchmark import mini_adapter as adapter

HAS_AGENT = all(importlib.util.find_spec(name) is not None for name in ("minisweagent", "litellm", "openai"))


class AdapterContractTests(unittest.TestCase):
    def test_config_rejects_wrong_endpoint_and_invalid_limits(self):
        for config in ({"api_base": "https://untrusted.example"}, {"max_steps": 0},
                       {"max_steps": True}, {"temperature": float("nan")},
                       {"api_key": "never-in-config"}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                adapter.validate_config(config)

    def test_config_matches_checked_in_profile(self):
        root = Path(__file__).resolve().parents[1]
        profile = json.loads((root / "configs/deepseek-v4-pro.json").read_text())
        self.assertEqual(adapter.validate_config(profile), adapter.DEFAULT_CONFIG)

    def test_redaction_nested_and_embedded(self):
        secret = "fixture-credential"
        value = {"api_key": secret, "nested": ["prefix " + secret], "authorization": "Bearer anything"}
        self.assertNotIn(secret, json.dumps(adapter.redact(value, secret)))
        self.assertEqual(adapter.redact(value, secret)["authorization"], "[REDACTED]")

    def test_unknown_usage_is_null(self):
        self.assertIsNone(adapter._usage_summary([])["total_tokens"])
        self.assertIsNone(adapter._usage_summary([None])["total_tokens"])
        self.assertEqual(adapter._usage_summary([{"total_tokens": 9}])["total_tokens"], 9)

    def test_container_identifier_cannot_be_shell_input(self):
        with self.assertRaises(ValueError):
            adapter.ExistingDockerEnvironment("container; injection")

    def test_commands_use_argument_list_and_no_host_environment_forwarding(self):
        captured = []
        def execute(argv, **kwargs):
            captured.append(argv)
            kwargs["stdout"].write(b"fixture output")
            return types.SimpleNamespace(returncode=0)
        with mock.patch.object(adapter.subprocess, "run", side_effect=execute):
            result = adapter.ExistingDockerEnvironment("d" * 64, 7).execute({"command": "printf 'a;b'"})
        self.assertEqual(result["output"], "fixture output")
        self.assertEqual(captured[0][-1], "printf 'a;b'")
        self.assertNotIn("-e", captured[0])
        self.assertIn("timeout", captured[0])
        self.assertIn("7", captured[0])


@unittest.skipUnless(HAS_AGENT, "Install requirements-agent.txt for real mini integration checks")
class RealMiniNoNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = mock.patch.dict(os.environ, {
            "MSWEA_GLOBAL_CONFIG_DIR": str(Path(self.temp.name) / "empty-config"),
            "MSWEA_SILENT_STARTUP": "1", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "DEEPSEEK_API_KEY": "fixture-credential-not-real",
        })
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()

    def _fake_transport(self, response_content, requests):
        def send(client, request, **kwargs):
            import httpx
            self.assertEqual(str(request.url), "https://api.deepseek.com/chat/completions")
            requests.append(json.loads(request.content))
            return httpx.Response(200, request=request, json={
                "id": "fixture-response", "object": "chat.completion", "created": 1,
                "model": "deepseek-v4-pro", "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": response_content},
                    "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            })
        return send

    def test_real_mini_and_sdk_use_expected_http_payload_without_network(self):
        from minisweagent.exceptions import Submitted
        requests = []

        class FakeEnvironment:
            def __init__(self, *args):
                pass
            def get_template_vars(self, **kwargs):
                return {"cwd": "/workspace"}
            def serialize(self):
                return {}
            def execute(self, action):
                if action["command"] != "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
                    raise AssertionError("Unexpected fixture action")
                raise Submitted({"role": "exit", "content": "",
                                 "extra": {"exit_status": "Submitted", "submission": ""}})

        content = "```mswea_bash_command\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        with mock.patch("httpx.Client.send", new=self._fake_transport(content, requests)), \
             mock.patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in test")), \
             mock.patch.object(adapter, "ExistingDockerEnvironment", FakeEnvironment):
            result = adapter.run_agent("Fixture issue", "a" * 64, Path(self.temp.name) / "out", {})
        self.assertEqual(result["exit_status"], "Submitted", result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["steps"], 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["model"], "deepseek-v4-pro")
        self.assertEqual(requests[0]["thinking"], {"type": "disabled"})
        self.assertEqual(requests[0]["temperature"], 0)
        self.assertEqual(requests[0]["max_tokens"], 4096)
        self.assertNotIn("tools", requests[0])
        self.assertEqual(result["usage"]["total_tokens"], 30)
        self.assertIsNone(result["cost_usd"])
        trajectory = (Path(self.temp.name) / "out/trajectory.json").read_text()
        self.assertNotIn("fixture-credential-not-real", trajectory)
        self.assertIsNone(json.loads(trajectory)["info"]["model_stats"]["instance_cost"])

    def test_malformed_responses_consume_steps_and_keep_usage(self):
        requests = []
        with mock.patch("httpx.Client.send", new=self._fake_transport("missing command", requests)), \
             mock.patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in test")):
            result = adapter.run_agent("Fixture issue", "b" * 64,
                Path(self.temp.name) / "format", {"max_steps": 2})
        self.assertEqual(result["exit_status"], "LimitsExceeded", result)
        self.assertEqual(result["steps"], 2)
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["usage"]["total_tokens"], 60)

    def test_transport_error_is_not_retried_or_leaked(self):
        attempts = []
        def fail(client, request, **kwargs):
            attempts.append(1)
            raise RuntimeError("fixture-credential-not-real")
        with mock.patch("httpx.Client.send", new=fail), \
             mock.patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in test")):
            result = adapter.run_agent("Fixture issue", "c" * 64,
                Path(self.temp.name) / "error", {})
        self.assertEqual(len(attempts), 1)
        self.assertEqual(result["status"], "agent_error")
        for path in (Path(self.temp.name) / "error").glob("*.json"):
            self.assertNotIn("fixture-credential-not-real", path.read_text())


if __name__ == "__main__":
    unittest.main()
