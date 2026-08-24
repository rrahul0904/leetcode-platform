from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from .practice import (
    PracticeStateTransitionError,
    published_question_payload,
    question_mode,
    question_runtime,
    question_tests,
    starter_source,
)
from .schemas import SubmissionRuntime


class RuntimeLinkVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimePackageEvidence:
    runtime: SubmissionRuntime
    public_tests: int
    hidden_tests: int
    package_hash: str


def _python_entrypoint(mode: dict[str, Any], starter: str) -> str:
    explicit = mode.get("entrypoint") or mode.get("function_name")
    if explicit is not None:
        value = str(explicit)
        if not value.isidentifier():
            raise RuntimeLinkVerificationError("Python entrypoint is invalid")
        return value
    try:
        parsed = ast.parse(starter)
    except SyntaxError as exc:
        raise RuntimeLinkVerificationError("Python starter code is invalid") from exc
    names = [
        node.name
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    if "solve" in names:
        return "solve"
    if len(names) == 1:
        return names[0]
    raise RuntimeLinkVerificationError("Python runtime package has no unambiguous entrypoint")


def validate_runtime_package(question: dict[str, Any]) -> RuntimePackageEvidence:
    """Validate the same structural facts required by the existing judge path."""
    try:
        runtime = question_runtime(question)
    except PracticeStateTransitionError as exc:
        raise RuntimeLinkVerificationError(str(exc)) from exc
    mode = question_mode(question)
    starter = starter_source(question, runtime)
    if not starter.strip():
        raise RuntimeLinkVerificationError("Runtime package is missing starter source")

    tests = question_tests(question, public_only=False)
    public_tests = sum(test.get("visibility") == "public" for test in tests)
    hidden_tests = sum(test.get("visibility") != "public" for test in tests)
    if public_tests < 1:
        raise RuntimeLinkVerificationError("Runtime package requires at least one public test")
    if hidden_tests < 1:
        raise RuntimeLinkVerificationError("Runtime package requires at least one hidden test")

    runtime_details: dict[str, object]
    if runtime is SubmissionRuntime.python:
        entrypoint = _python_entrypoint(mode, starter)
        runtime_details = {"entrypoint": entrypoint}
    elif runtime is SubmissionRuntime.postgresql:
        schema_sql = mode.get("schema_sql", mode.get("ddl"))
        seed_sql = mode.get("seed_sql", mode.get("seed_data", ""))
        timeout = mode.get("statement_timeout_ms", 5_000)
        if not isinstance(schema_sql, str) or not schema_sql.strip():
            raise RuntimeLinkVerificationError("SQL runtime package is missing trusted schema DDL")
        if not isinstance(seed_sql, str):
            raise RuntimeLinkVerificationError("SQL runtime seed data is invalid")
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or not 100 <= timeout <= 30_000
        ):
            raise RuntimeLinkVerificationError("SQL statement timeout is invalid")
        runtime_details = {
            "schema_sql": schema_sql,
            "seed_sql": seed_sql,
            "statement_timeout_ms": timeout,
        }
    else:  # pragma: no cover - question_runtime currently rejects other runtimes
        raise RuntimeLinkVerificationError("Unsupported runtime")

    identity = {
        "question_version_id": str(question.get("question_version_id") or ""),
        "runtime": runtime.value,
        "starter": starter,
        "tests": tests,
        "runtime_details": runtime_details,
    }
    package_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RuntimePackageEvidence(
        runtime=runtime,
        public_tests=public_tests,
        hidden_tests=hidden_tests,
        package_hash=package_hash,
    )


def verify_problem_runtime_link(
    connection: Connection,
    *,
    problem_id: UUID,
    question_slug: str,
) -> RuntimePackageEvidence:
    """Verify and persist the bridge without weakening source/publication gates."""
    source_state = (
        connection.execute(
            text(
                """
                SELECT p.publication_status, p.review_status,
                       count(ps.*) AS source_count,
                       bool_and(ps.disposition='hostable_licensed') AS all_hostable
                FROM knowledge_problems p
                LEFT JOIN knowledge_problem_sources ps ON ps.problem_id=p.id
                WHERE p.id=:problem_id AND p.deleted_at IS NULL
                GROUP BY p.id
                """
            ),
            {"problem_id": problem_id},
        )
        .mappings()
        .one_or_none()
    )
    if source_state is None:
        raise RuntimeLinkVerificationError("Knowledge problem does not exist")
    if source_state["publication_status"] != "published":
        raise RuntimeLinkVerificationError("Knowledge problem is not published")
    if int(source_state["source_count"]) < 1 or not bool(source_state["all_hostable"]):
        raise RuntimeLinkVerificationError(
            "Runtime link requires hostable-licensed provenance for every attached source"
        )

    try:
        question = published_question_payload(connection, question_slug)
    except Exception as exc:
        raise RuntimeLinkVerificationError("Published authored runtime question is unavailable") from exc
    evidence = validate_runtime_package(question)
    question_id = UUID(str(question["question_id"]))
    question_version_id = UUID(str(question["question_version_id"]))
    connection.execute(
        text(
            """
            INSERT INTO knowledge_problem_runtime_links (
                problem_id, question_id, question_version_id, runtime,
                link_status, package_hash, verification_metadata, verified_at,
                revoked_at
            ) VALUES (
                :problem_id, :question_id, :question_version_id, :runtime,
                'verified', :package_hash,
                jsonb_build_object(
                    'public_tests', :public_tests,
                    'hidden_tests', :hidden_tests,
                    'verification', 'runtime-package-v1'
                ),
                CURRENT_TIMESTAMP, NULL
            )
            ON CONFLICT (problem_id) DO UPDATE
            SET question_id=EXCLUDED.question_id,
                question_version_id=EXCLUDED.question_version_id,
                runtime=EXCLUDED.runtime,
                link_status='verified',
                package_hash=EXCLUDED.package_hash,
                verification_metadata=EXCLUDED.verification_metadata,
                verified_at=CURRENT_TIMESTAMP,
                revoked_at=NULL,
                updated_at=CURRENT_TIMESTAMP
            """
        ),
        {
            "problem_id": problem_id,
            "question_id": question_id,
            "question_version_id": question_version_id,
            "runtime": evidence.runtime.value,
            "package_hash": evidence.package_hash,
            "public_tests": evidence.public_tests,
            "hidden_tests": evidence.hidden_tests,
        },
    )
    return evidence


def revoke_problem_runtime_link(connection: Connection, *, problem_id: UUID) -> bool:
    return (
        connection.execute(
            text(
                """
                UPDATE knowledge_problem_runtime_links
                SET link_status='revoked', revoked_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE problem_id=:problem_id AND link_status <> 'revoked'
                RETURNING problem_id
                """
            ),
            {"problem_id": problem_id},
        ).scalar_one_or_none()
        is not None
    )
