#!/usr/bin/env python3
"""Publish only the deterministic first-party launch set with an audited bootstrap.

This is intentionally not a generic review bypass. It can run only in production,
requires an explicit one-shot enable flag and reason, accepts exactly the 50 IDs
owned by content_release_seed.py, revalidates packages and rights, verifies the
synced database hashes, and records an audit event for every publication.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from content_release_seed import ARCH_SPECS, PYTHON_SPECS, SQL_SPECS
from rigor_api.config import get_settings
from rigor_api.content_sync import discover_package_directories, load_package, validate_all
from rigor_api.database import create_database_engine
from sqlalchemy import Connection, text

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LAUNCH_PACKAGES = 50
BOOTSTRAP_ACTOR_SUBJECT = "system:production-launch-bootstrap"


def launch_ids() -> frozenset[str]:
    identifiers = {
        *(str(spec["id"]) for spec in PYTHON_SPECS),
        *(str(spec["id"]) for spec in SQL_SPECS),
        *(str(spec[0]) for spec in ARCH_SPECS),
    }
    if len(identifiers) != EXPECTED_LAUNCH_PACKAGES:
        raise RuntimeError(
            f"Production launch allowlist must contain exactly {EXPECTED_LAUNCH_PACKAGES} IDs; "
            f"found {len(identifiers)}"
        )
    return frozenset(identifiers)


def source_revision() -> str:
    explicit = os.getenv("GITHUB_SHA", "").strip()
    if explicit:
        return explicit[:64]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unknown"
    return (result.stdout.strip() if result.returncode == 0 else "unknown")[:64]


def require_bootstrap_authorization(environment: str) -> str:
    if environment.strip().lower() != "production":
        raise RuntimeError(
            "Production launch bootstrap is only allowed in RIGOR_ENVIRONMENT=production"
        )
    if os.getenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_ENABLED", "").strip().lower() != "true":
        raise RuntimeError("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_ENABLED=true is required")
    reason = os.getenv("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_REASON", "").strip()
    if len(reason) < 12:
        raise RuntimeError("RIGOR_PRODUCTION_LAUNCH_BOOTSTRAP_REASON must explain the release")
    return reason[:1000]


def validate_rights(directory: Path) -> str:
    rights_path = directory / "rights.json"
    if not rights_path.exists():
        raise RuntimeError(f"{directory.name}: rights.json is missing")
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    if rights.get("rights_basis") != "original":
        raise RuntimeError(f"{directory.name}: launch content must be first-party original")
    license_identifier = str(rights.get("license_identifier") or "")
    if license_identifier != "RIGOR-FIRST-PARTY-1.0":
        raise RuntimeError(f"{directory.name}: unexpected launch-content license")
    if not str(rights.get("certification") or "").strip():
        raise RuntimeError(f"{directory.name}: rights certification is missing")
    return license_identifier


def ensure_actor(connection: Connection) -> Any:
    return connection.execute(
        text(
            """
            INSERT INTO users(
                identity_subject, email, display_name, email_verified,
                auth_provider, status
            ) VALUES (
                :subject, 'production-launch-bootstrap@rigor.test',
                'Production Launch Bootstrap', true, 'system', 'active'
            )
            ON CONFLICT (identity_subject) DO UPDATE SET
                display_name=EXCLUDED.display_name,
                auth_provider='system',
                updated_at=CURRENT_TIMESTAMP
            RETURNING id
            """
        ),
        {"subject": BOOTSTRAP_ACTOR_SUBJECT},
    ).scalar_one()


def publish_launch_set(
    connection: Connection,
    *,
    content_root: Path,
    reason: str,
    revision: str,
) -> dict[str, Any]:
    targets = launch_ids()
    directories = {
        directory.name: directory for directory in discover_package_directories(content_root)
    }
    missing = sorted(targets - directories.keys())
    if missing:
        raise RuntimeError(f"Launch packages missing from source tree: {', '.join(missing)}")

    validation = validate_all(content_root, set(targets))
    invalid = [result for result in validation if result.status == "invalid"]
    if len(validation) != EXPECTED_LAUNCH_PACKAGES or invalid:
        details = "; ".join(
            f"{result.question_id}: {', '.join(result.findings)}" for result in invalid
        )
        raise RuntimeError(
            f"Launch validation failed: expected {EXPECTED_LAUNCH_PACKAGES}, "
            f"validated {len(validation)}, invalid {len(invalid)}. {details}"
        )

    packages = {identifier: load_package(directories[identifier]) for identifier in targets}
    licenses = {identifier: validate_rights(directories[identifier]) for identifier in targets}
    actor_id = ensure_actor(connection)
    published = 0
    unchanged = 0

    for identifier in sorted(targets):
        package = packages[identifier]
        row = (
            connection.execute(
                text(
                    """
                    SELECT q.id AS question_id, q.current_published_version_id,
                           v.id AS version_id, v.version, v.state::text AS state,
                           v.content_hash, v.source_revision,
                           (SELECT vr.status FROM validation_runs vr
                            WHERE vr.question_version_id=v.id
                            ORDER BY vr.started_at DESC LIMIT 1) AS validation_status
                    FROM questions q
                    JOIN question_versions v ON v.question_id=q.id
                    WHERE q.external_id=:external_id AND v.version=:version
                    FOR UPDATE OF q, v
                    """
                ),
                {"external_id": identifier, "version": package.question.version},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RuntimeError(f"{identifier}: validated package has not been synchronized")
        if str(row["content_hash"]) != package.content_hash:
            raise RuntimeError(f"{identifier}: database content hash does not match source package")
        if row["validation_status"] != "passed":
            raise RuntimeError(f"{identifier}: latest database validation is not passed")

        current_id = row["current_published_version_id"]
        version_id = row["version_id"]
        state = str(row["state"])
        if current_id == version_id and state == "published":
            unchanged += 1
            continue
        if current_id is not None and current_id != version_id:
            raise RuntimeError(
                f"{identifier}: another version is already published; bootstrap will not replace it"
            )
        if state != "awaiting_technical_review":
            raise RuntimeError(
                f"{identifier}: bootstrap accepts only awaiting_technical_review or "
                f"already-published versions; found {state}"
            )

        idempotency_key = (
            f"production-launch-bootstrap:{identifier}:{package.question.version}:"
            f"{package.content_hash[:16]}"
        )
        existing_event = connection.execute(
            text(
                "SELECT question_version_id FROM publication_events "
                "WHERE idempotency_key=:idempotency_key"
            ),
            {"idempotency_key": idempotency_key},
        ).scalar_one_or_none()
        if existing_event is not None and existing_event != version_id:
            raise RuntimeError(f"{identifier}: bootstrap idempotency key collision")

        if existing_event is None:
            connection.execute(
                text(
                    """
                    INSERT INTO publication_events(
                        question_version_id, published_by, idempotency_key,
                        source_revision, content_hash
                    ) VALUES (
                        :version_id, :actor_id, :idempotency_key,
                        :source_revision, :content_hash
                    )
                    """
                ),
                {
                    "version_id": version_id,
                    "actor_id": actor_id,
                    "idempotency_key": idempotency_key,
                    "source_revision": revision,
                    "content_hash": package.content_hash,
                },
            )
        connection.execute(
            text(
                "UPDATE question_versions SET state='published'::content_state, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=:version_id"
            ),
            {"version_id": version_id},
        )
        connection.execute(
            text(
                "UPDATE questions SET current_published_version_id=:version_id, "
                "archived_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=:question_id"
            ),
            {"version_id": version_id, "question_id": row["question_id"]},
        )
        connection.execute(
            text(
                """
                INSERT INTO audit_events(
                    actor_user_id, action, resource_type, resource_id,
                    details, correlation_id
                ) VALUES (
                    :actor_id, 'content.production_launch_bootstrapped',
                    'question_version', :resource_id, CAST(:details AS jsonb),
                    :correlation_id
                )
                """
            ),
            {
                "actor_id": actor_id,
                "resource_id": str(version_id),
                "details": json.dumps(
                    {
                        "external_id": identifier,
                        "version": package.question.version,
                        "content_hash": package.content_hash,
                        "source_revision": revision,
                        "reason": reason,
                        "rights_basis": "original",
                        "license_identifier": licenses[identifier],
                        "bootstrap_scope": "deterministic-first-party-launch-50",
                        "review_records_fabricated": False,
                    }
                ),
                "correlation_id": f"production-launch-{revision[:24]}",
            },
        )
        published += 1

    actual = int(
        connection.execute(
            text(
                """
                SELECT count(*)
                FROM questions q
                JOIN question_versions v ON v.id=q.current_published_version_id
                WHERE q.external_id=ANY(:ids)
                  AND v.state='published'::content_state
                """
            ),
            {"ids": sorted(targets)},
        ).scalar_one()
    )
    if actual != EXPECTED_LAUNCH_PACKAGES:
        raise RuntimeError(
            f"Expected {EXPECTED_LAUNCH_PACKAGES} published launch questions, found {actual}"
        )
    return {
        "expected": EXPECTED_LAUNCH_PACKAGES,
        "validated": len(validation),
        "published_now": published,
        "already_published": unchanged,
        "published_total": actual,
        "source_revision": revision,
        "bootstrap_scope": "deterministic-first-party-launch-50",
    }


def main() -> int:
    settings = get_settings()
    reason = require_bootstrap_authorization(settings.environment)
    revision = source_revision()
    engine = create_database_engine(settings)
    try:
        with engine.begin() as connection:
            result = publish_launch_set(
                connection,
                content_root=settings.content_root,
                reason=reason,
                revision=revision,
            )
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
