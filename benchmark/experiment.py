"""Explicitly opted-in model experiments, with immutable planned denominators."""
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import uuid

from .core import (ROOT, IMAGE, TASKS, check_process, digest, docker_base, docker_image,
                   fixture_hash, get_task, grade, prepare, read_json, task_list, write_json)
from .process import execute
from . import environment


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def run_experiment(args):
    if not args.allow_paid:
        raise ValueError("Model calls require --allow-paid; list/validate/selftest/prepare/grade are free")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("Set DEEPSEEK_API_KEY in the host environment (value is never displayed)")
    try:
        installed_version = importlib.metadata.version("mini-swe-agent")
    except importlib.metadata.PackageNotFoundError:
        raise ValueError("Install requirements-agent.txt in the selected Python environment") from None
    if installed_version != "2.4.6":
        raise ValueError("Install pinned requirements-agent.txt before running")
    config_path = Path(args.config).resolve()
    config = read_json(config_path)
    from .mini_adapter import validate_config
    config = validate_config(config)
    if config.get("model") != "deepseek-v4-pro" or config.get("api_base") != "https://api.deepseek.com":
        raise ValueError("Use official DeepSeek V4 Pro configuration")
    wall = config.get("wall_time_seconds", 900)
    if not isinstance(wall, (int, float)) or not 10 <= wall <= 3600:
        raise ValueError("wall_time_seconds must be 10..3600")
    if not 1 <= args.repetitions <= 20:
        raise ValueError("repetitions must be 1..20")
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError("Run output must not exist; choose a new experiment name")
    image_info = docker_image(args.image)
    # Always use resolved content-addressed image, never a mutable tag after preflight.
    image = image_info["id"]
    tasks = task_list() if args.task == "all" else [get_task(args.task)]
    attempts = [{"task_id": task["id"], "repetition": rep,
                 "directory": f"{task['id']}/rep-{rep:02d}"}
                for rep in range(1, args.repetitions + 1) for task in tasks]
    output.mkdir(parents=True)
    packages = sorted(f"{dist.metadata['Name']}=={dist.version}" for dist in importlib.metadata.distributions())
    revision = execute(["git", "rev-parse", "HEAD"], timeout=10, cwd=ROOT)
    dirty = execute(["git", "status", "--porcelain", "--untracked-files=no"], timeout=10, cwd=ROOT)
    write_json(output / "plan.json", {"schema_version": 1, "started_at": timestamp(),
               "benchmark_version": "1.0.0", "python": platform.python_version(),
               "git_commit": revision["stdout"].strip() if revision["returncode"] == 0 else None,
               "git_dirty": bool(dirty["stdout"].strip()),
               "platform": platform.platform(), "config": config, "config_sha256": digest(config_path),
               "manifest_sha256": digest(TASKS / "manifest.json"),
               "fixture_sha256": {task["id"]: fixture_hash(task) for task in tasks},
               "harness_sha256": {p.name: digest(p) for p in sorted((ROOT / "benchmark").glob("*.py"))},
               "image": image_info, "packages": packages, "attempts": attempts})
    # Preserve full resolved dependency versions, without index URLs or credentials.
    (output / "packages.txt").write_text("\n".join(packages) + "\n", encoding="utf-8")
    for attempt in attempts:
        task = get_task(attempt["task_id"])
        folder = output / attempt["directory"]
        folder.mkdir(parents=True)
        started = time.monotonic()
        name = "swe-task-" + uuid.uuid4().hex[:16]
        container = None
        result = {"task_id": task["id"], "repetition": attempt["repetition"],
                  "status": "infra_error", "resolved": False, "partial_score": 0,
                  "started_at": timestamp()}
        write_json(folder / "result.json", result)
        print(f"Running {task['id']} repetition {attempt['repetition']}", flush=True)
        try:
            container = environment.provision(task, folder, name, image)
            payload = {"task": (TASKS / task["id"] / "issue.md").read_text(encoding="utf-8"),
                       "container_id": container, "output_dir": str(folder), "config": config,
                       "result_path": str(folder / "agent.json")}
            write_json(folder / "worker-input.json", payload)
            worker_env = {key: value for key, value in os.environ.items()
                          if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "DEEPSEEK_API_KEY"}}
            worker_env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
            worker = execute([sys.executable, "-m", "benchmark.worker", str(folder / "worker-input.json")],
                             timeout=wall, cwd=ROOT, env=worker_env)
            # Defensive redaction before saving child diagnostics, never save host environment.
            secret = os.environ["DEEPSEEK_API_KEY"]
            for stream in ["stdout", "stderr"]:
                (folder / f"worker-{stream}.log").write_text(worker[stream].replace(secret, "[REDACTED]"), encoding="utf-8")
            # Stop every process in the candidate container before exporting immutable files.
            exported = folder / "submission"
            environment.export_submission(container, exported)
            agent_path = folder / "agent.json"
            agent = read_json(agent_path) if agent_path.exists() else {"status": "worker_error"}
            result.update(grade(task, exported, docker=True, image=image), agent=agent)
            # A time/budget/API failure cannot count as autonomous completed resolution,
            # even if a partial patch happens to pass. Keep functional evidence separately.
            result["functional_resolved"] = result["resolved"]
            if worker["timed_out"] or worker["returncode"] != 0 or agent.get("status") != "completed":
                result.update(status="timed_out" if worker["timed_out"] else "agent_error",
                              resolved=False, partial_score=0)
            if "submission" in result:
                (folder / "submission.diff").write_text(result["submission"].pop("patch"), encoding="utf-8")
        except Exception as exc:
            # Do not stringify SDK exceptions here: they may contain provider diagnostics.
            result.update(status="infra_error", error_type=type(exc).__name__, resolved=False, partial_score=0)
        finally:
            try:
                cleanup = execute(["docker", "rm", "-f", "-v", name], timeout=30)
                result["cleanup"] = {"returncode": cleanup["returncode"], "timed_out": cleanup["timed_out"]}
            except Exception as exc:
                result["cleanup"] = {"error_type": type(exc).__name__, "returncode": None}
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            result["finished_at"] = timestamp()
            write_json(folder / "result.json", result)
        print(f"  {result['status']}", flush=True)
    return output
