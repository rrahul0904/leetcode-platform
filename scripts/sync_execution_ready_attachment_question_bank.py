#!/usr/bin/env python3
"""Sync execution-enriched attachment questions using the governed V1 importer.

Python questions are marked runnable only when the execution-bank builder has
validated at least one public and one hidden reference test. SQL candidates
remain non-runnable until PostgreSQL confirmation changes their validation
status from ``postgres_confirmation_pending`` to ``reference_validated``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

import scripts.sync_attachment_question_bank as base

base.VERSION = "attachment-v2-execution"
_original_validate = base.validate_row
_original_structured = base.question_structured_content
_original_upsert = base.upsert_one


def _tests_are_governed(row: dict[str, Any]) -> bool:
    mode = row.get("mode_specification")
    if not isinstance(mode, dict):
        return False
    tests = mode.get("tests")
    if not isinstance(tests, list):
        return False
    public = sum(isinstance(test, dict) and test.get("visibility") == "public" for test in tests)
    hidden = sum(isinstance(test, dict) and test.get("visibility") == "hidden" for test in tests)
    return public > 0 and hidden > 0


def _list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        return [item.strip() for item in re.split(r"[|\n]", stripped) if item.strip()]
    return [str(value).strip()]


def validate_row(row: dict[str, Any]) -> list[str]:
    runnable = bool(row.get("runnable"))
    row["runnable"] = False
    findings = _original_validate(row)
    row["runnable"] = runnable
    if runnable and not _tests_are_governed(row):
        findings.append("runnable question must have at least one public and one hidden test")
    if runnable and str(row.get("execution_validation_status")) != "reference_validated":
        findings.append("runnable question has not completed runtime-specific reference validation")
    return findings


def question_structured_content(row: dict[str, Any], track_slug: str) -> dict[str, Any]:
    content = _original_structured(row, track_slug)
    is_runnable = (
        bool(row.get("runnable"))
        and str(row.get("execution_validation_status")) == "reference_validated"
        and _tests_are_governed(row)
    )
    expected_approach = str(row.get("expected_approach") or "").strip()
    requirements = str(row.get("requirements") or "").strip()
    content.update(
        {
            "mode_specification": row.get("mode_specification"),
            "runnable": is_runnable,
            "execution_validation_status": row.get("execution_validation_status"),
            "execution_bank_version": 2,
            # PublishedCatalogRepository expects these to be arrays. Keep them
            # source-derived or empty rather than inventing curriculum content.
            "learning_objectives": [expected_approach] if expected_approach else [],
            "prerequisites": [],
            "candidate_instructions": [requirements] if requirements else [],
            "constraints": _list_value(row.get("constraints")),
        }
    )
    return content


def _skill_values(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("subject", "platform", "topic", "subtopic"):
        value = str(row.get(key) or "").strip()
        if value:
            values.append(value)
    tags = row.get("tags")
    if isinstance(tags, list):
        values.extend(str(tag) for tag in tags)
    elif isinstance(tags, str) and tags.strip():
        try:
            decoded = json.loads(tags)
            if isinstance(decoded, list):
                values.extend(str(tag) for tag in decoded)
            else:
                values.append(tags)
        except json.JSONDecodeError:
            values.extend(re.split(r"[,|]", tags))
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _skill_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:100]


def upsert_one(connection, row: dict[str, Any], *, source_revision: str, publish: bool):
    result = _original_upsert(
        connection,
        row,
        source_revision=source_revision,
        publish=publish,
    )
    if result[0] == "unseeded_track":
        return result
    version_id = connection.execute(
        text(
            """
            SELECT v.id
            FROM questions q JOIN question_versions v ON v.question_id=q.id
            WHERE q.external_id=:external_id AND v.version=:version
            """
        ),
        {"external_id": str(row["canonical_id"]), "version": base.VERSION},
    ).scalar_one_or_none()
    if version_id is None:
        return result
    connection.execute(
        text("DELETE FROM question_skills WHERE question_version_id=:version_id"),
        {"version_id": version_id},
    )
    for value in _skill_values(row):
        slug = _skill_slug(value)
        if not slug:
            continue
        skill_id = connection.execute(
            text(
                """
                INSERT INTO skills (slug, name, category)
                VALUES (:slug, :name, 'attachment')
                ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                RETURNING id
                """
            ),
            {"slug": slug, "name": value[:200]},
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO question_skills (question_version_id, skill_id)
                VALUES (:version_id, :skill_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"version_id": version_id, "skill_id": skill_id},
        )
    return result


base.validate_row = validate_row
base.question_structured_content = question_structured_content
base.upsert_one = upsert_one


if __name__ == "__main__":
    raise SystemExit(base.main())
