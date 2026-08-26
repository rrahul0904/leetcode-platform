from __future__ import annotations

import subprocess
import sys


def test_library_import_does_not_boot_fastapi_application() -> None:
    """CLI/library consumers must not initialize the serving application.

    This protects collectors and release tooling from evaluating production-only
    serving settings simply because they import a repository/service module.
    """

    code = """
import sys
import rigor_api.question_intelligence  # noqa: F401
assert 'rigor_api.main' not in sys.modules
assert 'rigor_api.legacy_main' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
