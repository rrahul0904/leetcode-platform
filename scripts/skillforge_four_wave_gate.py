"""Fail-closed four-wave SkillForge release evidence validator.

Validates receipt shape and consistency, never attests that GitHub or AWS
actually performed the claimed behavior. Independent live replay is mandatory.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_LEDGER = (
    Path(__file__).resolve().parents[1]
    / "docs/platform/skillforge_four_wave_gate_status.json"
)
REQUIRED_GATES = {
    "L01": "W2", "L02": "W2", "L03": "W4", "L04": "W2", "L05": "W3",
    "L06": "W3", "L07": "W3", "L08": "W3", "L09": "W4", "L10": "W4",
}
WAVE_IDS = ("W1", "W2", "W3", "W4")
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class GateError(ValueError):
    """Invalid or insufficient release evidence."""


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_url(value: object) -> bool:
    if not _nonblank(value):
        return False
    parsed = urlparse(str(value))
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def _verify_receipt(receipt: Any, release_sha: str, builder: str, gate_id: str) -> None:
    if not isinstance(receipt, dict):
        raise GateError(f"{gate_id}: receipt must be an object")
    if receipt.get("release_sha") != release_sha:
        raise GateError(f"{gate_id}: receipt SHA is not the immutable release SHA")
    reviewer = receipt.get("reviewer")
    if not _nonblank(reviewer) or str(reviewer).casefold() == builder.casefold():
        raise GateError(f"{gate_id}: independent reviewer required")
    if not _safe_url(receipt.get("evidence_url")):
        raise GateError(f"{gate_id}: HTTPS evidence URL required")
    if not _nonblank(receipt.get("environment")):
        raise GateError(f"{gate_id}: observed test environment required")
    if not _nonblank(receipt.get("negative_case")):
        raise GateError(f"{gate_id}: reproducible negative-control receipt required")
    if not isinstance(receipt.get("artifact_sha256"), str) or not DIGEST.fullmatch(
        receipt["artifact_sha256"]
    ):
        raise GateError(f"{gate_id}: artifact SHA-256 digest required")
    try:
        observed = datetime.fromisoformat(str(receipt["observed_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise GateError(f"{gate_id}: invalid observed_at timestamp") from exc
    if observed.tzinfo is None or observed > datetime.now(UTC):
        raise GateError(f"{gate_id}: observed_at must be timezone-aware and not future")


def validate(
    ledger: Any, *, ready: bool = False, release_sha: str | None = None
) -> dict[str, Any]:
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        raise GateError("unsupported four-wave release ledger version")
    if ledger.get("repository") != "rrahul0904/leetcode-platform":
        raise GateError("incorrect canonical shipping repository")
    if ledger.get("production_target") != "AWS":
        raise GateError("production target must remain AWS, not Vercel/Railway/Render")
    builder = ledger.get("builder")
    if not _nonblank(builder):
        raise GateError("implementation builder identity required")
    waves = ledger.get("waves")
    if (
        not isinstance(waves, list)
        or [w.get("id") for w in waves if isinstance(w, dict)] != list(WAVE_IDS)
    ):
        raise GateError("four ordered implementation waves required")
    if any(w.get("status") not in {"blocked", "building", "verified"} for w in waves):
        raise GateError("invalid wave lifecycle state")
    gates = ledger.get("gates")
    if not isinstance(gates, list) or len(gates) != len(REQUIRED_GATES):
        raise GateError("exactly ten launch gates required")
    gate_ids = [g.get("id") for g in gates if isinstance(g, dict)]
    if len(gate_ids) != len(set(gate_ids)) or set(gate_ids) != set(REQUIRED_GATES):
        raise GateError("missing, duplicated or unrecognized launch gate")
    expected_sha = release_sha or ledger.get("release_sha")
    if expected_sha is not None and (
        not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha)
    ):
        raise GateError("release SHA must be a full immutable 40-character Git commit")
    if release_sha is not None and ledger.get("release_sha") != release_sha:
        raise GateError("requested release SHA differs from ledger release SHA")
    verified = 0
    for gate in gates:
        gate_id = gate["id"]
        if gate.get("wave") != REQUIRED_GATES[gate_id]:
            raise GateError(f"{gate_id}: assigned to incorrect wave")
        state = gate.get("status")
        receipts = gate.get("evidence")
        if state not in {"blocked", "verified"} or not isinstance(receipts, list):
            raise GateError(f"{gate_id}: invalid gate status or evidence list")
        if state == "blocked":
            if not _nonblank(gate.get("reason")):
                raise GateError(f"{gate_id}: blocked gate needs a concrete reason")
            if receipts:
                raise GateError(f"{gate_id}: do not attach passing receipts to a blocked gate")
        else:
            if not expected_sha or not receipts:
                raise GateError(f"{gate_id}: verified gate requires pinned SHA and evidence")
            for receipt in receipts:
                _verify_receipt(receipt, expected_sha, str(builder), gate_id)
            verified += 1
    if ready and (
        verified != len(REQUIRED_GATES)
        or any(w["status"] != "verified" for w in waves)
    ):
        raise GateError("NO-GO: all ten gates and all four waves must be verified before launch")
    return {
        "verdict": (
            "RECEIPTS_VALIDATION_PASSED_REQUIRES_INDEPENDENT_REVIEW"
            if ready
            else "NO_GO_PENDING_LIVE_CERTIFICATION"
        ),
        "gate_count": len(REQUIRED_GATES),
        "verified_gates": verified,
        "blocked_gates": len(REQUIRED_GATES) - verified,
        "release_sha": expected_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--assert-ready", action="store_true")
    parser.add_argument("--release-sha", type=str)
    args = parser.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        result = validate(ledger, ready=args.assert_ready, release_sha=args.release_sha)
    except (OSError, ValueError) as exc:
        print(f"FAIL CLOSED: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
