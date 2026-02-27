#!/usr/bin/env python3
"""Run test suites and emit machine-readable artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULT_DIR = os.path.join(ROOT, "artifacts", "test-results")
LOG_DIR = os.path.join(ROOT, "artifacts", "logs")


class TrackingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_start: Dict[str, float] = {}
        self.records: Dict[str, Dict[str, object]] = {}

    def startTest(self, test):
        tid = test.id()
        self.test_start[tid] = time.perf_counter()
        self.records[tid] = {"status": "passed", "message": "", "duration": 0.0}
        super().startTest(test)

    def _mark(self, test, status: str, err=None):
        tid = test.id()
        rec = self.records.setdefault(tid, {"status": "passed", "message": "", "duration": 0.0})
        rec["status"] = status
        if err:
            rec["message"] = self._exc_info_to_string(err, test)

    def addFailure(self, test, err):
        self._mark(test, "failed", err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self._mark(test, "error", err)
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._mark(test, "skipped")
        super().addSkip(test, reason)

    def stopTest(self, test):
        tid = test.id()
        start = self.test_start.get(tid, time.perf_counter())
        self.records[tid]["duration"] = time.perf_counter() - start
        super().stopTest(test)


class TrackingRunner(unittest.TextTestRunner):
    resultclass = TrackingResult


def iter_tests(suite: unittest.TestSuite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_tests(test)
        else:
            yield test


def discover(paths: List[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    root_suite = unittest.TestSuite()
    for path in paths:
        root_suite.addTests(loader.discover(path, pattern="test_*.py", top_level_dir=ROOT))
    return root_suite


def write_junit(suite_name: str, result: TrackingResult, tests: List[unittest.TestCase], elapsed: float) -> str:
    os.makedirs(RESULT_DIR, exist_ok=True)
    xml_path = os.path.join(RESULT_DIR, f"junit-{suite_name}.xml")

    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)

    root = ET.Element(
        "testsuite",
        name=suite_name,
        tests=str(len(tests)),
        failures=str(failures),
        errors=str(errors),
        skipped=str(skipped),
        time=f"{elapsed:.6f}",
    )

    for test in tests:
        tid = test.id()
        rec = result.records.get(tid, {"status": "passed", "message": "", "duration": 0.0})
        case = ET.SubElement(
            root,
            "testcase",
            classname=".".join(tid.split(".")[:-1]),
            name=tid.split(".")[-1],
            time=f"{float(rec.get('duration', 0.0)):.6f}",
        )
        status = rec.get("status")
        if status == "failed":
            node = ET.SubElement(case, "failure", message="failure")
            node.text = str(rec.get("message", ""))
        elif status == "error":
            node = ET.SubElement(case, "error", message="error")
            node.text = str(rec.get("message", ""))
        elif status == "skipped":
            ET.SubElement(case, "skipped")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    return xml_path


def load_commit_sha() -> str:
    head = os.path.join(ROOT, ".git", "HEAD")
    if not os.path.exists(head):
        return "unknown"
    with open(head, "r", encoding="utf-8") as f:
        ref = f.read().strip()
    if ref.startswith("ref:"):
        ref_path = os.path.join(ROOT, ".git", ref.split(" ", 1)[1])
        if os.path.exists(ref_path):
            with open(ref_path, "r", encoding="utf-8") as rf:
                return rf.read().strip()
    return ref


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["unit", "contract", "e2e", "mod-bridge", "all"])
    args = parser.parse_args()

    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    suite_map: Dict[str, List[str]] = {
        "unit": [os.path.join(ROOT, "tests", "unit")],
        "contract": [os.path.join(ROOT, "tests", "contract")],
        "e2e": [os.path.join(ROOT, "tests", "e2e")],
        "mod-bridge": [os.path.join(ROOT, "tests", "mod_bridge")],
        "all": [
            os.path.join(ROOT, "tests", "unit"),
            os.path.join(ROOT, "tests", "contract"),
            os.path.join(ROOT, "tests", "e2e"),
            os.path.join(ROOT, "tests", "mod_bridge"),
        ],
    }

    paths = suite_map[args.suite]
    suite = discover(paths)
    all_tests = list(iter_tests(suite))

    start = time.perf_counter()
    runner = TrackingRunner(verbosity=2)
    result: TrackingResult = runner.run(suite)
    elapsed = time.perf_counter() - start

    write_junit(args.suite, result, all_tests, elapsed)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "run_id": run_id,
        "commit_sha": load_commit_sha(),
        "suite": args.suite,
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failed": len(result.failures) + len(result.errors),
        "skipped": len(result.skipped),
        "duration_ms": int(elapsed * 1000),
        "error_codes": {
            "ASSERTION_FAILURE": len(result.failures),
            "UNEXPECTED_ERROR": len(result.errors),
        },
        "manual_tests": 0,
        "ai_tests": result.testsRun,
    }

    summary_path = os.path.join(RESULT_DIR, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log_path = os.path.join(LOG_DIR, f"jarvis-test-{run_id}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False, indent=2))
        f.write("\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
