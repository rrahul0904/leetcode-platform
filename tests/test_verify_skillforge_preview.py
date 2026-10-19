from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_skillforge_preview import (  # noqa: E402
    PreviewVerificationError,
    parse_claimed_identity,
    verify_deployment_metadata,
)

HOST = "skillforge-platform-2705hmh8s-rrahul0904-5013s-projects.vercel.app"
SHA = "b1e31a13f8760e71f899d5f6d00e5d7628c83843"
ORIGIN = f"https://{HOST}"


def valid_deployment() -> dict:
    return {
        "id": "dpl_test123",
        "url": HOST,
        "projectId": "prj_cKifcPIyHvvuL6EZAgvUC8mpbQEq",
        "target": None,
        "readyState": "READY",
        "meta": {
            "githubCommitSha": SHA,
            "githubOrg": "rrahul0904",
            "githubRepo": "leetcode-platform",
        },
    }


def test_accepts_exact_verified_preview() -> None:
    result = verify_deployment_metadata(ORIGIN, SHA, valid_deployment())
    assert result["deployment_sha"] == SHA
    assert result["url"] == ORIGIN


@pytest.mark.parametrize("url", [
    "http://" + HOST,
    "https://attacker.com",
    "https://skillforge-reconstruction-2705hmh8s-rrahul0904-5013s-projects.vercel.app",
    ORIGIN + "/api/backend/livez",
    ORIGIN + "?x=1",
    "https://user@" + HOST,
    "https://" + HOST + ":443",
])
def test_rejects_unsafe_origin(url: str) -> None:
    with pytest.raises(PreviewVerificationError):
        parse_claimed_identity(url, SHA)


@pytest.mark.parametrize("mutation", [
    {"projectId": "prj_other"},
    {"url": "skillforge-platform-other-rrahul0904-5013s-projects.vercel.app"},
    {"target": "production"},
    {"readyState": "ERROR"},
    {"meta": {
        "githubCommitSha": "a" * 40,
        "githubOrg": "rrahul0904",
        "githubRepo": "leetcode-platform",
    }},
    {"meta": {}},
    {"id": ""},
])
def test_rejects_mismatched_or_incomplete_deployment(mutation: dict) -> None:
    payload = valid_deployment() | mutation
    with pytest.raises(PreviewVerificationError):
        verify_deployment_metadata(ORIGIN, SHA, payload)


def test_accepts_project_nested_id() -> None:
    payload = valid_deployment()
    del payload["projectId"]
    payload["project"] = {"id": "prj_cKifcPIyHvvuL6EZAgvUC8mpbQEq"}
    assert verify_deployment_metadata(ORIGIN, SHA, payload)["status"] == "READY"
