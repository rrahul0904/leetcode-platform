"""Fail-closed identity check for a SkillForge Vercel Preview deployment.

Run from the protected GitHub Preview-health workflow before HTTP smoke probes.
The expected commit SHA is a *claim* until checked against Vercel metadata.
"""

from __future__ import annotations

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

PROJECT_ID = "prj_cKifcPIyHvvuL6EZAgvUC8mpbQEq"
TEAM_ID = "team_zmEezpOKGZy2sH5nqTfO44LD"
SUFFIX = "-rrahul0904-5013s-projects.vercel.app"
PREFIX = "skillforge-platform-"


class PreviewVerificationError(ValueError):
    """A Preview failed the exact deployment identity gate."""


def parse_claimed_identity(origin: str, sha: str) -> str:
    parsed = urlsplit(origin)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host.startswith(PREFIX)
        or not host.endswith(SUFFIX)
        or parsed.netloc != host
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise PreviewVerificationError("Preview origin is not an exact SkillForge project URL")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise PreviewVerificationError("Expected SHA must be a full lowercase Git commit")
    return host


def verify_deployment_metadata(origin: str, sha: str, payload: dict) -> dict:
    host = parse_claimed_identity(origin, sha)
    project = payload.get("project") or {}
    project_id = payload.get("projectId") or project.get("id")
    meta = payload.get("meta") or {}
    deployed_sha = meta.get("githubCommitSha")

    if project_id != PROJECT_ID or payload.get("url") != host:
        raise PreviewVerificationError("Deployment belongs to a different project or URL")
    if payload.get("target") not in (None, "preview"):
        raise PreviewVerificationError("Production cannot substitute for Preview evidence")
    if (payload.get("readyState") or payload.get("state")) != "READY":
        raise PreviewVerificationError("Deployment is not READY")
    if (
        meta.get("githubOrg") != "rrahul0904"
        or meta.get("githubRepo") != "leetcode-platform"
    ):
        raise PreviewVerificationError("Deployment is not sourced from the canonical repository")
    if deployed_sha != sha:
        raise PreviewVerificationError("Deployment Git commit differs from claimed SHA")
    if not isinstance(payload.get("id"), str) or not payload["id"].startswith("dpl_"):
        raise PreviewVerificationError("Vercel deployment ID is missing")

    return {
        "deployment_id": payload["id"],
        "project_id": project_id,
        "deployment_sha": deployed_sha,
        "url": f"https://{host}",
        "status": "READY",
    }


def fetch_metadata(host: str, token: str) -> dict:
    endpoint = f"https://api.vercel.com/v13/deployments/{quote(host, safe='')}?teamId={TEAM_ID}"
    request = Request(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urlopen(request, timeout=25) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise PreviewVerificationError("Invalid Vercel deployment metadata")
    return payload


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: verify_skillforge_preview.py <deployment-origin> <full-git-sha>",
            file=sys.stderr,
        )
        return 2
    origin, sha = sys.argv[1:]
    try:
        host = parse_claimed_identity(origin, sha)
        token = os.environ.get("VERCEL_READ_TOKEN", "")
        if not token:
            raise PreviewVerificationError(
                "Vercel read token unavailable; exact-SHA probe is blocked"
            )
        proof = verify_deployment_metadata(origin, sha, fetch_metadata(host, token))
    except (PreviewVerificationError, HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Preview identity gate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
