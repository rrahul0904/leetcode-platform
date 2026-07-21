#!/usr/bin/env python3
"""Execute trusted platform-authored reference solution tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tests = sorted((ROOT / "content" / "questions").glob("**/test_reference.py"))
    if not tests:
        print("no executable reference solution packages found")
        return 0
    command = [sys.executable, "-m", "pytest", "-q", *[str(path) for path in tests]]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
