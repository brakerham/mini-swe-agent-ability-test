"""Trusted child runner. Candidate source is imported only in this child."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.events.append({"id": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.events.append({"id": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.events.append({"id": test.id(), "status": "error"})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.events.append({"id": test.id(), "status": "skipped"})

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.events.append({"id": test.id(), "status": "expected_failure"})

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.events.append({"id": test.id(), "status": "unexpected_success"})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.events.append({"id": test.id(), "status": "failed_subtest"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--suite", choices=["public", "FeatureTests", "RegressionTests"], required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.workspace / "src"))
    if args.suite == "public":
        suite = unittest.defaultTestLoader.discover(str(args.workspace / "tests"))
    else:
        spec = importlib.util.spec_from_file_location("test_acceptance", args.evaluator)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(getattr(module, args.suite))
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    print("BENCHMARK_RESULT=" + json.dumps({"tests_run": result.testsRun,
          "events": result.events, "successful": result.wasSuccessful()}), flush=True)
    return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__ == "__main__":
    raise SystemExit(main())
