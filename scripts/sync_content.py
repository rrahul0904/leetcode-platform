#!/usr/bin/env python3
"""Validate or synchronize canonical Git-authored question packages."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from rigor_api.config import get_settings
from rigor_api.content_sync import ContentSynchronizer
from rigor_api.database import create_database_engine

ROOT = Path(__file__).resolve().parents[1]


def source_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "docker-image"
    return result.stdout.strip() if result.returncode == 0 else "working-tree"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("validate", "dry-run", "sync", "rollback"), default="validate"
    )
    parser.add_argument("--question-id", action="append", dest="question_ids")
    parser.add_argument("--version", help="Previously published version used by rollback mode")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "reports" / "content-sync-report.json"
    )
    args = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        synchronizer = ContentSynchronizer(engine, settings.content_root, source_revision())
        if args.mode == "rollback":
            if not args.question_ids or len(args.question_ids) != 1 or not args.version:
                parser.error("rollback requires exactly one --question-id and --version")
            report = synchronizer.rollback(args.question_ids[0], args.version)
        else:
            report = synchronizer.run(
                mode=args.mode, selected_ids=set(args.question_ids) if args.question_ids else None
            )
    finally:
        engine.dispose()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.to_json(), encoding="utf-8")
    print(report.to_json(), end="")
    return 1 if report.invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
