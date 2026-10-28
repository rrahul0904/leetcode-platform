"""Atomic, retry-safe final code grading outbox for employer assessments.

Submission and dispatch intent commit together. A browser closing immediately
after receiving a submit response cannot cause a coding question to be ungraded.
The queue never receives confidential tests or candidate source code.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, text


def code_request_digest(
    *,
    attempt_id: UUID,
    version_id: UUID,
    question_number: int,
    mode: str,
    source_hash: str,
) -> str:
    encoded = json.dumps(
        {
            "attempt_id": str(attempt_id),
            "version_id": str(version_id),
            "question_number": question_number,
            "mode": mode,
            "source_sha256": source_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def enqueue_submitted_code_grades(
    connection: Connection,
    *,
    attempt: dict[str, Any],
) -> int:
    """Enqueue all saved coding answers in the *same* DB transaction as submit.

    Caller holds FOR UPDATE lock on the owned attempt, and has just set its
    status to submitted. A repeated submission may safely call this function
    again; the unique final-question index prevents duplicate grading.
    """
    if attempt["status"] != "submitted":
        return 0
    questions = attempt["candidate_blueprint"]["questions"]
    code_languages = {
        int(question["number"]): question["language"]
        for question in questions
        if question["kind"] == "code" and question.get("language") in {"python", "sql"}
    }
    if not code_languages:
        return 0
    attempt_id = UUID(str(attempt["id"]))
    version_id = UUID(str(attempt["assessment_version_id"]))
    candidate_id = UUID(str(attempt["candidate_id"]))
    saved = connection.execute(
        text(
            """SELECT question_number, answer_text, answer_sha256
               FROM employer_assessment_responses
               WHERE attempt_id=:attempt AND candidate_id=:candidate
               ORDER BY question_number"""
        ),
        {"attempt": attempt_id, "candidate": candidate_id},
    ).mappings().all()
    created = 0
    for answer in saved:
        number = int(answer["question_number"])
        if number not in code_languages:
            continue
        source = str(answer["answer_text"])
        if not source.strip():
            continue
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if source_hash != answer["answer_sha256"]:
            raise ValueError("Saved coding response integrity verification failed")
        if len(source.encode("utf-8")) > 100_000:
            raise ValueError("Saved coding response exceeds the execution source limit")
        execution_id = uuid4()
        recorded = connection.execute(
            text(
                """INSERT INTO employer_code_executions
                      (id, organization_id, candidate_id, attempt_id,
                       assessment_version_id, question_number, language,
                       execution_mode, idempotency_key, request_sha256,
                       source_sha256, source_code)
                   SELECT :id, a.organization_id, :candidate, a.id, :version,
                          :number, :language, 'SUBMIT', :key, :request_hash,
                          :source_hash, :source
                   FROM employer_assessment_attempts a
                   WHERE a.id=:attempt AND a.candidate_id=:candidate
                     AND a.status='submitted'
                   ON CONFLICT DO NOTHING
                   RETURNING id"""
            ),
            {
                "id": execution_id,
                "attempt": attempt_id,
                "candidate": candidate_id,
                "version": version_id,
                "number": number,
                "language": code_languages[number],
                "key": f"final-{attempt_id}-{number}",
                "request_hash": code_request_digest(
                    attempt_id=attempt_id, version_id=version_id,
                    question_number=number, mode="SUBMIT", source_hash=source_hash,
                ),
                "source_hash": source_hash,
                "source": source,
            },
        ).scalar_one_or_none()
        if recorded is None:
            continue
        connection.execute(
            text(
                """INSERT INTO employer_code_execution_outbox (execution_id)
                   VALUES (:execution)"""
            ),
            {"execution": recorded},
        )
        created += 1
    return created
