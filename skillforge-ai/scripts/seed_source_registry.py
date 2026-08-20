#!/usr/bin/env python3
"""Load ADDITIONAL_SOURCE_REGISTRY.json into Supabase content_sources.

This intentionally registers provenance/rights metadata only. It does not copy
source problem statements or solution code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "content-manifest" / "ADDITIONAL_SOURCE_REGISTRY.json"


def slug(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if part)


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    from supabase import create_client

    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = []
    for source in payload["sources"]:
        archive = source["archive"]
        rows.append({
            "source_key": slug(archive.removesuffix(".zip")),
            "display_name": archive.removesuffix(".zip"),
            "archive_name": archive,
            "rights_state": source["rights_state"],
            "license_name": source.get("license"),
            "notes": source.get("use"),
            "metadata": {
                "kind": source.get("kind", []),
                "observed_scale": source.get("observed_scale"),
                "registry_policy_version": payload.get("policy_version"),
            },
        })

    client = create_client(url, key)
    result = client.table("content_sources").upsert(rows, on_conflict="source_key").execute()
    print(json.dumps({"registered_sources": len(result.data or [])}, indent=2))


if __name__ == "__main__":
    main()
