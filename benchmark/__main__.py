import argparse
import json
from pathlib import Path
import sys

from .core import (IMAGE, get_task, grade, prepare, report, selftest, task_list,
                   validate, write_json)


def main(argv=None):
    parser = argparse.ArgumentParser(description="SWE capability benchmark; no model calls without run --allow-paid")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("validate")
    selfcheck = commands.add_parser("selftest")
    selfcheck.add_argument("--docker", action="store_true")
    selfcheck.add_argument("--image", default=IMAGE)
    selfcheck.add_argument("--output")
    prep = commands.add_parser("prepare")
    prep.add_argument("--task", required=True)
    prep.add_argument("--output", required=True)
    grading = commands.add_parser("grade")
    grading.add_argument("--task", required=True)
    grading.add_argument("--candidate", required=True)
    grading.add_argument("--output", required=True)
    grading.add_argument("--docker", action="store_true", help="Required for untrusted submissions; local mode is trusted calibration only")
    grading.add_argument("--image", default=IMAGE)
    run = commands.add_parser("run")
    run.add_argument("--task", default="all")
    run.add_argument("--output", required=True)
    run.add_argument("--config", default="configs/deepseek-v4-pro.json")
    run.add_argument("--repetitions", type=int, default=1)
    run.add_argument("--image", default=IMAGE)
    run.add_argument("--allow-paid", action="store_true")
    reporting = commands.add_parser("report")
    reporting.add_argument("--runs", required=True)
    reporting.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for task in task_list():
                print(f"{task['id']:18} {task['difficulty']:8} {task['category']:18} {task['title']}")
            return 0
        if args.command == "validate":
            data = validate()
        elif args.command == "selftest":
            data = selftest(docker=args.docker, image=args.image)
        elif args.command == "prepare":
            data = {"status": "prepared", "files": prepare(get_task(args.task), Path(args.output))}
        elif args.command == "grade":
            data = grade(get_task(args.task), Path(args.candidate), docker=args.docker, image=args.image)
        elif args.command == "run":
            from .experiment import run_experiment
            output = run_experiment(args)
            data = report(output)
            write_json(output / "report.json", data)
            print(json.dumps({key: value for key, value in data.items() if key != "attempts"}, indent=2))
            return 0
        else:
            data = report(args.runs)
        if getattr(args, "output", None) and args.command != "prepare":
            write_json(args.output, data)
        # Keep verbose evidence in JSON rather than flooding the console.
        summary = {key: value for key, value in data.items() if key not in {"tasks", "attempts", "suites", "submission", "files"}}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.command == "grade":
            return 0 if data["resolved"] else 1
        return 1 if data.get("status") == "failed" else 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
