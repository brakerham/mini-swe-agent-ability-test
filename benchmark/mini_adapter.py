"""Pinned mini-swe-agent integration. No optional libraries load until run_agent.

The model lives on the host. The existing-container environment never forwards
host variables or mounts host paths. The caller owns container lifetime and the
hard outer wall-time limit. All model retries are disabled (including mini's
usual tenacity retry loop) so one agent step is at most one API request.
"""
from __future__ import annotations

import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

EXPECTED_VERSIONS = {"mini-swe-agent": "2.4.6", "litellm": "1.93.1", "openai": "2.26.0"}
DEFAULT_CONFIG = {
    "model": "deepseek-v4-pro", "api_base": "https://api.deepseek.com",
    "thinking": "disabled", "temperature": 0.0, "max_steps": 60,
    "max_output_tokens": 4096, "request_timeout_seconds": 90,
    "command_timeout_seconds": 30, "wall_time_seconds": 900,
}
SYSTEM_TEMPLATE = """You are a software engineer working in /workspace.
Solve the issue using the source, documentation and public tests available there.
Each response must contain exactly one bash command in this format:
```mswea_bash_command
your_command_here
```
Commands run independently in /workspace. Directory changes do not persist.
You may explain your next action briefly before the command.
When finished, issue exactly: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
"""
INSTANCE_TEMPLATE = """{{task}}

Inspect the existing implementation and tests, implement the issue, and check
your changes. The external evaluator accepts only the source paths stated in the
issue. You may add local tests for your own use; they do not replace the grader.
Run the public tests with PYTHONPATH=src python -m unittest discover -s tests -v.
"""


def validate_config(config: dict) -> dict:
    """Validate before dependency imports or credential access."""
    unknown = set(config) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError("Unknown model configuration keys: " + ", ".join(sorted(unknown)))
    checked = DEFAULT_CONFIG | config
    if checked["model"] != "deepseek-v4-pro":
        raise ValueError("This benchmark profile requires model deepseek-v4-pro")
    if checked["api_base"] != "https://api.deepseek.com":
        raise ValueError("This profile requires the official DeepSeek HTTPS endpoint")
    if checked["thinking"] not in ("disabled", "enabled"):
        raise ValueError("thinking must be disabled or enabled")
    for name in ("max_steps", "max_output_tokens", "request_timeout_seconds",
                 "command_timeout_seconds", "wall_time_seconds"):
        value = checked[name]
        if type(value) is not int or value <= 0:
            raise ValueError(name + " must be a positive integer")
    temperature = checked["temperature"]
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature must be finite and between 0 and 2")
    return checked


def redact(value, secret: str):
    """Redact the supplied key and credential fields before any persistence."""
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in {"api_key", "authorization", "access_token"}
            else redact(item, secret) for key, item in value.items()
        }
    return value


class ExistingDockerEnvironment:
    """The mini Environment protocol for a caller-owned, credential-free container."""

    def __init__(self, container_id: str, timeout: int = 30):
        if not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
            raise ValueError("Expected a Docker container ID")
        self.container_id = container_id
        self.timeout = timeout

    def get_template_vars(self, **kwargs):
        return {"cwd": "/workspace", **kwargs}

    def serialize(self):
        return {"info": {"config": {"environment": {
            "type": "existing-docker", "cwd": "/workspace", "command_timeout_seconds": self.timeout,
            "host_environment_forwarded": False,
        }}}}

    def execute(self, action: dict, cwd: str = "") -> dict:
        command = action.get("command", "")
        if not isinstance(command, str):
            raise ValueError("Agent command must be a string")
        started = time.monotonic()
        # timeout runs INSIDE the container and kills the command's process group.
        argv = ["docker", "exec", "-w", "/workspace", self.container_id,
                "timeout", "--signal=KILL", "--kill-after=1", str(self.timeout),
                "bash", "-lc", command]
        with tempfile.TemporaryFile() as capture:
            try:
                result = subprocess.run(argv, stdout=capture, stderr=subprocess.STDOUT,
                                        timeout=self.timeout + 10, check=False)
                code = result.returncode
                exception_info = ""
            except subprocess.TimeoutExpired:
                code = -1
                exception_info = "Docker command exceeded its outer deadline"
            capture.seek(0, 2)
            size = capture.tell()
            capture.seek(0)
            raw = capture.read(15000)
            if size > 15000:
                capture.seek(-5000, 2)
                raw = raw[:10000] + b"\n[output truncated]\n" + capture.read(5000)
        output = raw.decode("utf-8", errors="replace")
        lines = output.lstrip().splitlines(keepends=True)
        if code == 0 and lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
            from minisweagent.exceptions import Submitted
            submission = "".join(lines[1:])
            raise Submitted({"role": "exit", "content": submission,
                             "extra": {"exit_status": "Submitted", "submission": submission}})
        return {"output": output, "returncode": code, "exception_info": exception_info,
                "extra": {"elapsed_seconds": round(time.monotonic() - started, 3),
                          "output_truncated": size > 15000}}


def _model_class():
    """A mini Model protocol shim using DeepSeek's documented compatible SDK.

    Upstream text parsing is retained. A direct client avoids LiteLLM's model
    registry downloads, tokenizer downloads, pricing estimates and retries.
    """
    from minisweagent.exceptions import FormatError
    from minisweagent.models.utils.actions_text import parse_regex_actions, format_observation_messages
    from openai import OpenAI

    class DeepSeekTextModel:
        def __init__(self, config, secret):
            self.profile = config
            self.client = OpenAI(api_key=secret, base_url=config["api_base"],
                timeout=config["request_timeout_seconds"], max_retries=0,
                organization="", project="")
            self.usage_records = []
            self.response_models = []

        def query(self, messages: list[dict], **kwargs) -> dict:
            # Exactly one SDK call per step. No retries or fallback models.
            prepared = [{"role": message["role"], "content": message["content"]}
                        for message in messages]
            response = self.client.chat.completions.create(model=self.profile["model"],
                messages=prepared, temperature=self.profile["temperature"],
                max_tokens=self.profile["max_output_tokens"],
                extra_body={"thinking": {"type": self.profile["thinking"]}})
            usage = response.usage.model_dump() if response.usage is not None else None
            self.usage_records.append(usage)
            self.response_models.append(response.model)
            extra = {"cost": 0.0, "cost_usd": None, "cost_tracking": "unavailable",
                     "usage": usage, "response": response.model_dump(), "timestamp": time.time()}
            try:
                actions = parse_regex_actions(response.choices[0].message.content or "",
                    action_regex=r"```mswea_bash_command\s*\n(.*?)\n```",
                    format_error_template="Expected exactly one mswea_bash_command block; got {{actions|length}}.")
            except FormatError as exc:
                exc.messages[0].setdefault("extra", {}).update(extra)
                raise
            message = response.choices[0].message.model_dump()
            message["extra"] = {**extra, "actions": actions}
            return message

        def format_message(self, **kwargs):
            return kwargs

        def format_observation_messages(self, message, outputs, template_vars=None):
            return format_observation_messages(outputs, template_vars=template_vars,
                observation_template="<returncode>{{output.returncode}}</returncode>\n"
                    "<exception>{{output.exception_info}}</exception>\n<output>{{output.output}}</output>")

        def get_template_vars(self, **kwargs):
            return {"model_name": self.profile["model"], **kwargs}

        def serialize(self):
            return {"info": {"config": {"model": self.profile,
                "model_type": "benchmark.mini_adapter.DeepSeekTextModel",
                "credential_source": "host:DEEPSEEK_API_KEY"}}}

    return DeepSeekTextModel


def _agent_class(secret: str):
    from minisweagent.agents.default import DefaultAgent

    class SafeAgent(DefaultAgent):
        def serialize(self, *extra_dicts):
            data = super().serialize(*extra_dicts)
            stats = data["info"]["model_stats"]
            stats["instance_cost"] = None
            stats["cost_tracking"] = "unavailable"
            return redact(data, secret)

        def handle_uncaught_exception(self, exc):
            # SDK exception text can contain request headers; keep only the class.
            return self.add_messages({"role": "exit", "content": type(exc).__name__,
                "extra": {"exit_status": type(exc).__name__, "submission": ""}})

    return SafeAgent


def _usage_summary(records: list) -> dict:
    totals = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = [record.get(field) for record in records if isinstance(record, dict)]
        totals[field] = sum(values) if len(values) == len(records) and records and all(
            type(value) is int for value in values) else None
    totals["responses_with_usage"] = sum(isinstance(record, dict) for record in records)
    return totals


def run_agent(task: str, container_id: str, output_dir: Path, config: dict) -> dict:
    """Run one paid attempt. Caller must explicitly authorize before calling.

    ``output_dir/trajectory.json`` is updated after every step. Cost is null,
    because this profile does not claim provider billing accuracy or a dollar
    spending cap. Step/output/wall-time limits bound work but not exact spend.
    """
    checked = validate_config(config)
    for package, version in EXPECTED_VERSIONS.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            raise RuntimeError("Install requirements-agent.txt before a paid run") from None
        if actual != version:
            raise RuntimeError(f"Expected {package}=={version}; found {actual}")
    secret = os.environ.get("DEEPSEEK_API_KEY", "")
    if not secret.strip():
        raise RuntimeError("Set DEEPSEEK_API_KEY in the host environment")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Avoid loading the user's mini global .env or displaying its location.
    os.environ["MSWEA_GLOBAL_CONFIG_DIR"] = str((output_dir / "mini-config-empty").resolve())
    os.environ["MSWEA_SILENT_STARTUP"] = "1"
    model_type = _model_class()
    model = model_type(checked, secret)
    agent_type = _agent_class(secret)
    agent = agent_type(model, ExistingDockerEnvironment(container_id, checked["command_timeout_seconds"]),
        system_template=SYSTEM_TEMPLATE, instance_template=INSTANCE_TEMPLATE,
        step_limit=checked["max_steps"], cost_limit=0.0,
        wall_time_limit_seconds=checked["wall_time_seconds"], max_consecutive_format_errors=3,
        output_path=output_dir / "trajectory.json")
    started = time.monotonic()
    try:
        result = agent.run(task)
        exit_status = result.get("exit_status", "Unknown")
    except Exception as exc:
        exit_status = type(exc).__name__
    finally:
        model.client.close()
    summary = {
        "status": "completed" if exit_status == "Submitted" else "agent_error",
        "exit_status": exit_status, "steps": agent.n_calls,
        "usage": _usage_summary(model.usage_records), "cost_usd": None,
        "cost_tracking": "unavailable", "model": checked["model"],
        "response_models": sorted(set(model.response_models)), "config": checked,
        "versions": EXPECTED_VERSIONS, "elapsed_seconds": round(time.monotonic() - started, 3),
        "harness_variations": ["DeepSeek OpenAI-compatible SDK Model protocol shim",
            "upstream mini text action parser", "existing-container environment", "API retries disabled",
            "unknown provider cost", "credential redaction"],
    }
    safe_summary = redact(summary, secret)
    (output_dir / "agent.json").write_text(json.dumps(safe_summary, indent=2), encoding="utf-8")
    return safe_summary
