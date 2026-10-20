"""Fail-closed SkillForge V1 release evidence contract.

This checks structure and traceability, NOT the truth of remote test results.
Evidence URLs must still be independently inspected before any promotion.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

REPOSITORY = "rrahul0904/leetcode-platform"
VERCEL_PROJECT_ID = "prj_cKifcPIyHvvuL6EZAgvUC8mpbQEq"
DEFAULT_CONTRACT = (
    Path(__file__).resolve().parents[1] / "docs/release/skillforge_v1_gate_status.json"
)

# Ordered dependency gates. A later verified gate requires all earlier gates.
GATES: tuple[tuple[str, str], ...] = (
    ("source_ci", "P0"),
    ("preview_identity", "P1"),
    ("preview_http", "P1"),
    ("hosted_clerk_journey", "P2"),
    ("two_account_rls", "P2"),
    ("reviewed_content_catalog", "P3"),
    ("python_run_submit", "P3"),
    ("sql_run_submit", "P3"),
    ("adversarial_execution", "P3"),
    ("candidate_browser_uat", "P4"),
    ("admin_browser_uat", "P4"),
    ("mobile_accessibility", "P4"),
    ("backup_restore", "P5"),
    ("staged_production", "P5"),
    ("production_postpromotion", "P5"),
)
PRE_RELEASE_GATES = tuple(gate for gate, _ in GATES[:-1])
DEPLOYMENT_GATES = {
    "preview_identity",
    "preview_http",
    "staged_production",
    "production_postpromotion",
}


class ContractError(ValueError):
    """The release record is malformed or makes an unsupported claim."""


def require_object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ContractError(f"{location} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ContractError(f"{location} requires string property names")
    return cast(dict[str, object], value)


def require_text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ContractError(f"{location} must be nonempty trimmed text")
    return value


def require_sha(value: object, location: str) -> str:
    text = require_text(value, location)
    if re.fullmatch(r"[0-9a-f]{40}", text) is None:
        raise ContractError(f"{location} must be a full Git SHA")
    return text


def require_evidence_url(value: object, location: str) -> str:
    url = require_text(value, location)
    parsed = urlsplit(url)
    prefix = f"/{REPOSITORY}/actions/runs/"
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.startswith(prefix)
        or re.fullmatch(r"[1-9][0-9]*", parsed.path[len(prefix):]) is None
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ContractError(f"{location} must link to an exact GitHub Actions run")
    return url


def require_utc(value: object, location: str) -> None:
    raw = require_text(value, location)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{location} must be an ISO-8601 timestamp") from exc
    if not raw.endswith("Z") or parsed.tzinfo != timezone.utc:
        raise ContractError(f"{location} must be explicit UTC (Z)")


def validate_document(value: object) -> dict[str, object]:
    doc = require_object(value, "release contract")
    if set(doc) != {"schema_version", "repository", "vercel_project_id", "release_sha", "gates"}:
        raise ContractError("release contract has missing or unknown top-level fields")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ContractError("unsupported release schema")
    if doc["repository"] != REPOSITORY or doc["vercel_project_id"] != VERCEL_PROJECT_ID:
        raise ContractError("release contract has wrong repository or canonical Vercel project")

    release_sha = doc["release_sha"]
    if release_sha is not None:
        require_sha(release_sha, "release_sha")

    records = require_object(doc["gates"], "gates")
    if set(records) != {name for name, _ in GATES}:
        raise ContractError("release gates differ from mandatory V1 gate inventory")

    seen_blocked = False
    for gate, _phase in GATES:
        record = require_object(records[gate], f"gates.{gate}")
        state = record.get("status")
        if state == "blocked":
            if set(record) != {"status", "reason"}:
                raise ContractError(f"{gate}: blocked gate requires only status and reason")
            require_text(record["reason"], f"gates.{gate}.reason")
            seen_blocked = True
            continue
        if state != "verified":
            raise ContractError(f"{gate}: status must be blocked or verified")
        if seen_blocked:
            raise ContractError(f"{gate}: cannot pass while an earlier dependency is blocked")
        if release_sha is None:
            raise ContractError(f"{gate}: a verified gate requires release_sha")
        if set(record) != {"status", "evidence"}:
            raise ContractError(f"{gate}: verified gate requires only status and evidence")

        proof = require_object(record["evidence"], f"gates.{gate}.evidence")
        required = {"sha", "run_url", "observed_at_utc", "reviewed_by"}
        if gate in DEPLOYMENT_GATES:
            required.add("deployment_id")
        if set(proof) != required:
            raise ContractError(f"{gate}: evidence keys do not match required fields")
        if require_sha(proof["sha"], f"{gate}.sha") != release_sha:
            raise ContractError(f"{gate}: evidence SHA does not match release SHA")
        require_evidence_url(proof["run_url"], f"{gate}.run_url")
        require_utc(proof["observed_at_utc"], f"{gate}.observed_at_utc")
        require_text(proof["reviewed_by"], f"{gate}.reviewed_by")
        if gate in DEPLOYMENT_GATES:
            deployment_id = require_text(proof["deployment_id"], f"{gate}.deployment_id")
            if re.fullmatch(r"dpl_[A-Za-z0-9]+", deployment_id) is None:
                raise ContractError(f"{gate}: invalid Vercel deployment ID")

    return doc


def release_progress(doc: dict[str, object]) -> tuple[list[str], list[str]]:
    records = require_object(doc["gates"], "gates")
    verified = [name for name, _ in GATES
                if require_object(records[name], name)["status"] == "verified"]
    blocked = [name for name, _ in GATES if name not in verified]
    return verified, blocked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_CONTRACT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--assert-pre-release", action="store_true")
    mode.add_argument("--assert-complete", action="store_true")
    args = parser.parse_args(argv)
    try:
        document: object = json.loads(args.file.read_text(encoding="utf-8"))
        valid = validate_document(document)
        verified, blocked = release_progress(valid)
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        print(f"INVALID_RELEASE_EVIDENCE: {exc}", file=sys.stderr)
        return 2

    if args.validate:
        print(f"VALID_SCHEMA: {len(GATES)} mandatory gates; no completion claim")
        return 0
    if args.report:
        print(json.dumps({
            "state": "BLOCKED" if blocked else "DOCUMENTED_FOR_INDEPENDENT_REVIEW",
            "verified": verified,
            "blocked": blocked,
            "release_sha": valid["release_sha"],
            "remote_evidence_independently_verified": False,
        }, sort_keys=True))
        return 0

    required = PRE_RELEASE_GATES if args.assert_pre_release else tuple(
        name for name, _ in GATES
    )
    missing = [name for name in required if name in blocked]
    if missing:
        print(f"RELEASE_BLOCKED: missing evidence for {', '.join(missing)}", file=sys.stderr)
        return 1
    print("DOCUMENTED_GATE_SET_COMPLETE; independent live evidence review still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
