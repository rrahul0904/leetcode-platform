#!/usr/bin/env python3
"""Run executable content packages in isolated import namespaces.

Question packages deliberately own their reference implementation and tests.
Executing one package per subprocess prevents common filenames such as
``reference.py`` and ``test_reference.py`` from colliding in Python's module
cache while still producing one release-level pass/fail result.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTION_ROOT = ROOT / "content" / "questions"


def main() -> int:
    tests = sorted(QUESTION_ROOT.glob("**/test_reference.py"))
    if not tests:
        print("No executable content reference tests were found.", file=sys.stderr)
        return 1

    failures: list[Path] = []
    for test_path in tests:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_path.name],
            cwd=test_path.parent,
            check=False,
        )
        if result.returncode != 0:
            failures.append(test_path.relative_to(ROOT))

    if failures:
        print("Content reference tests failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Content reference tests passed: {len(tests)} isolated package(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
