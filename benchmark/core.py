"""Fixture integrity, pristine grading, calibration, and denominator-safe reports."""
import ast
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .process import execute

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
IMAGE = "mini-swe-benchmark:v1"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_list():
    return read_json(TASKS / "manifest.json")["tasks"]


def get_task(task_id):
    for task in task_list():
        if task["id"] == task_id:
            return task
    raise ValueError(f"Unknown task: {task_id}")


def ignored(path):
    return any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts) or path.suffix == ".pyc"


def inventory(root):
    root = Path(root)
    def is_link(path):
        return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
    if is_link(root) or not root.is_dir():
        raise ValueError("Candidate must be a real directory, not a symlink")
    for parent in root.absolute().parents:
        if is_link(parent):
            raise ValueError("Symlink in candidate root path")
    files = {}
    for path in root.rglob("*"):
        if is_link(path):
            raise ValueError(f"Symlink/junction forbidden: {path.relative_to(root)}")
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_file():
            if path.stat().st_size > 1_000_000:
                raise ValueError(f"File exceeds 1 MB: {relative}")
            files[relative.as_posix()] = digest(path)
        elif not path.is_dir():
            raise ValueError(f"Special file forbidden: {relative}")
    return files


def fixture_hash(task):
    root = TASKS / task["id"]
    hashes = inventory(root)
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def prepare(task, output):
    output = Path(output)
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    shutil.copytree(TASKS / task["id"] / "candidate", output,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git"))
    shutil.copyfile(TASKS / task["id"] / "issue.md", output / "ISSUE.md")
    return inventory(output)


def submission(task, candidate):
    """Allow source changes and authored tests, but grade original tests only."""
    candidate = Path(candidate)
    actual = inventory(candidate)
    with tempfile.TemporaryDirectory() as temp:
        baseline = Path(temp) / "baseline"
        expected = prepare(task, baseline)
        changes = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
        violations = []
        source = set(task["allowed_paths"])
        for name in changes:
            path = Path(name)
            authored_test = name.startswith("tests/") and path.suffix == ".py"
            if name not in source and not authored_test:
                violations.append(f"Protected or unexpected file: {name}")
            if name in source and name not in actual:
                violations.append(f"Required source deleted: {name}")
        patch = []
        for name in changes:
            before = (baseline / name).read_text(encoding="utf-8").splitlines(keepends=True) if name in expected else []
            after = (candidate / name).read_text(encoding="utf-8").splitlines(keepends=True) if name in actual else []
            patch.extend(difflib.unified_diff(before, after, fromfile="a/" + name, tofile="b/" + name))
        return {"valid": not violations, "violations": violations,
                "changed_files": changes, "sha256": actual, "patch": "".join(patch),
                "authored_test_files": [x for x in changes if x.startswith("tests/")]}


def expected_tests(task, suite):
    """Count expected method IDs without importing any candidate code."""
    root = TASKS / task["id"]
    files = list((root / "candidate" / "tests").glob("test*.py")) if suite == "public" else [root / "evaluator" / "test_acceptance.py"]
    found = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (suite == "public" or node.name == suite):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith("test"):
                        found.append(f"{path.stem}.{node.name}.{method.name}")
    return sorted(found)


def docker_base():
    return ["--network", "none", "--cpus", "1", "--memory", "512m", "--pids-limit", "128",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--user", "65534:65534"]


def check_process(result, label):
    if result["timed_out"] or result["returncode"] != 0:
        raise RuntimeError(f"{label} failed: {result['stderr'][-2000:]}")
    return result["stdout"].strip()


def docker_image(image=IMAGE):
    raw = check_process(execute(["docker", "image", "inspect", image], timeout=30), "Image inspection")
    data = json.loads(raw)[0]
    return {"id": data["Id"], "repo_digests": data.get("RepoDigests", []),
            "os": data["Os"], "architecture": data["Architecture"]}


def run_suite(task, workspace, suite, *, docker=False, image=IMAGE):
    root = TASKS / task["id"]
    runner = ROOT / "benchmark" / "test_runner.py"
    evaluator = root / "evaluator" / "test_acceptance.py"
    expected = expected_tests(task, suite)
    if docker:
        import uuid
        name = "swe-grade-" + uuid.uuid4().hex[:16]
        command = ["docker", "run", "--rm", "--name", name, *docker_base(),
                   "--mount", f"type=bind,src={workspace.resolve()},dst=/workspace,readonly",
                   "--mount", f"type=bind,src={evaluator.resolve()},dst=/eval/test_acceptance.py,readonly",
                   "--mount", f"type=bind,src={runner.resolve()},dst=/eval/runner.py,readonly",
                   image, "python", "-B", "-I", "/eval/runner.py", "--workspace", "/workspace",
                   "--evaluator", "/eval/test_acceptance.py", "--suite", suite]
        try:
            process = execute(command, timeout=45)
        finally:
            execute(["docker", "rm", "-f", "-v", name], timeout=20)
    else:
        command = [sys.executable, "-B", "-I", str(runner), "--workspace", str(workspace),
                   "--evaluator", str(evaluator), "--suite", suite]
        safe_env = {key: value for key, value in os.environ.items()
                    if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG"}}
        safe_env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
        process = execute(command, timeout=30, cwd=workspace, env=safe_env)
    records = [line.removeprefix("BENCHMARK_RESULT=") for line in process["stdout"].splitlines()
               if line.startswith("BENCHMARK_RESULT=")]
    parsed = None
    if len(records) == 1:
        try:
            parsed = json.loads(records[0])
        except ValueError:
            pass
    primary_events = [x for x in parsed.get("events", []) if x.get("status") != "failed_subtest"] if isinstance(parsed, dict) else []
    # A failing subtest has no addSuccess/addFailure callback for its parent.
    subtest_parents = {x.get("id") for x in parsed.get("events", []) if x.get("status") == "failed_subtest"} if isinstance(parsed, dict) else set()
    primary_ids = [x.get("id", "") for x in primary_events]
    observed = primary_ids + list(subtest_parents - set(primary_ids))
    complete = (isinstance(parsed, dict) and parsed.get("tests_run") == len(expected)
                and sorted(observed) == expected and bool(expected))
    passed = sum(x.get("status") == "passed" for x in parsed.get("events", [])) if isinstance(parsed, dict) else 0
    status = "timed_out" if process["timed_out"] else "passed" if complete and process["returncode"] == 0 and passed == len(expected) else "failed" if complete else "invalid_result"
    return {"status": status, "passed": passed if complete else 0, "expected": len(expected),
            "expected_ids": expected, "result": parsed, **process}


def grade(task, candidate, *, docker=False, image=IMAGE):
    result = {"task_id": task["id"], "fixture_sha256": fixture_hash(task),
              "execution": "docker" if docker else "local_trusted_only", "resolved": False, "partial_score": 0.0}
    try:
        change = submission(task, candidate)
    except (ValueError, OSError, UnicodeError) as exc:
        return {**result, "status": "invalid_submission", "error": str(exc)}
    result["submission"] = change
    if not change["valid"]:
        return {**result, "status": "invalid_submission"}
    with tempfile.TemporaryDirectory(prefix="swe-grade-") as temp:
        workspace = Path(temp) / "candidate"
        prepare(task, workspace)
        for relative in task["allowed_paths"]:
            shutil.copyfile(Path(candidate) / relative, workspace / relative)
        if docker:
            result["image"] = docker_image(image)
        suites = {name: run_suite(task, workspace, name, docker=docker, image=image)
                  for name in ["public", "RegressionTests", "FeatureTests"]}
    result["suites"] = suites
    regression_ok = all(suites[x]["status"] == "passed" for x in ["public", "RegressionTests"])
    feature = suites["FeatureTests"]
    result["resolved"] = regression_ok and feature["status"] == "passed"
    result["partial_score"] = feature["passed"] / feature["expected"] if regression_ok and feature["expected"] else 0.0
    result["status"] = "resolved" if result["resolved"] else "timed_out" if any(s["status"] == "timed_out" for s in suites.values()) else "invalid_result" if any(s["status"] == "invalid_result" for s in suites.values()) else "unresolved"
    return result


def validate():
    tasks = task_list()
    if len(tasks) != 6 or len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("v1 requires six unique tasks")
    summaries = []
    for task in tasks:
        root = TASKS / task["id"]
        for field in ["id", "title", "category", "difficulty", "weight", "allowed_paths", "public_command"]:
            if not task.get(field):
                raise ValueError(f"Missing {field}")
        if task["weight"] != 1:
            raise ValueError("v1 uses equal task weights")
        for relative in task["allowed_paths"]:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not relative.startswith("src/"):
                raise ValueError("Invalid source allowlist")
            if not (root / "candidate" / path).is_file() or not (root / "gold" / path).is_file():
                raise ValueError(f"Missing candidate/gold source {relative}")
        if set(inventory(root / "gold")) != set(task["allowed_paths"]):
            raise ValueError("Gold files must exactly match source allowlist")
        if len((root / "issue.md").read_text(encoding="utf-8")) < 100:
            raise ValueError("Missing meaningful issue")
        counts = {name: len(expected_tests(task, name)) for name in ["public", "RegressionTests", "FeatureTests"]}
        if not all(counts.values()):
            raise ValueError("Each suite must contain tests")
        summaries.append({"task_id": task["id"], "tests": counts, "sha256": fixture_hash(task)})
    return {"status": "passed", "tasks": summaries}


def selftest(*, docker=False, image=IMAGE):
    validate()
    results = []
    for task in task_list():
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "candidate"
            prepare(task, candidate)
            baseline = grade(task, candidate, docker=docker, image=image)
            for relative in task["allowed_paths"]:
                shutil.copyfile(TASKS / task["id"] / "gold" / relative, candidate / relative)
            gold = grade(task, candidate, docker=docker, image=image)
        passed = (baseline["suites"]["public"]["status"] == "passed"
                  and baseline["suites"]["RegressionTests"]["status"] == "passed"
                  and baseline["suites"]["FeatureTests"]["status"] == "failed"
                  and gold["resolved"])
        results.append({"task_id": task["id"], "passed": passed, "baseline": baseline, "gold": gold})
    return {"status": "passed" if all(x["passed"] for x in results) else "failed", "tasks": results}


def report(runs):
    runs = Path(runs)
    plan = read_json(runs / "plan.json")
    attempts = []
    for item in plan["attempts"]:
        path = runs / item["directory"] / "result.json"
        result = read_json(path) if path.is_file() else {"status": "missing", "resolved": False, "partial_score": 0}
        attempts.append({**item, "result": result})
    total = len(attempts)
    if not total:
        raise ValueError("Plan has no attempts")
    solved = sum(x["result"].get("resolved") is True for x in attempts)
    # Wilson interval is descriptive; repeat outcomes are not independent tasks.
    z = 1.96
    p = solved / total
    center = (p + z*z/(2*total)) / (1+z*z/total)
    half = z*((p*(1-p)/total+z*z/(4*total*total))**0.5)/(1+z*z/total)
    per_task = {}
    for item in attempts:
        per_task.setdefault(item["task_id"], []).append(item["result"])
    task_rates = {key: sum(x.get("resolved") is True for x in values)/len(values) for key, values in per_task.items()}
    categories = {}
    for item in attempts:
        category = get_task(item["task_id"])["category"]
        categories.setdefault(category, []).append(item["result"].get("resolved") is True)
    known_costs = [x["result"].get("agent", {}).get("cost_usd") for x in attempts]
    numeric_costs = [x for x in known_costs if isinstance(x, (int, float))]
    return {"schema_version": 1, "planned": total, "resolved": solved,
            "resolved_rate": p, "macro_task_resolved_rate": sum(task_rates.values()) / len(task_rates),
            "all_repetitions_resolved_rate": sum(rate == 1 for rate in task_rates.values()) / len(task_rates),
            "descriptive_wilson_95": [max(0, center-half), min(1, center+half)],
            "interval_caveat": "Small public synthetic suite; repetitions share tasks and are correlated.",
            "partial_score_mean": sum(x["result"].get("partial_score", 0) for x in attempts) / total,
            "status_counts": dict(Counter(x["result"].get("status", "unknown") for x in attempts)),
            "per_task_resolved_rate": task_rates,
            "per_category_resolved_rate": {key: sum(values)/len(values) for key, values in categories.items()},
            "known_cost_usd": sum(numeric_costs) if numeric_costs else None,
            "attempts_with_known_cost": len(numeric_costs), "attempts": attempts}
