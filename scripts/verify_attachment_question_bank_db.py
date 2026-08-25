#!/usr/bin/env python3
"""Release-gate verification for an attachment question-bank PostgreSQL sync."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from sqlalchemy import create_engine, text


@dataclass
class Verification:
    expected_questions: int
    questions: int
    versions: int
    solutions: int
    explanations: int
    unique_external_ids: int
    published: int
    runnable: int
    runnable_with_public_tests: int
    runnable_with_hidden_tests: int
    search_documents: int
    subject_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    seniority_counts: dict[str, int]
    indexes: list[str]
    failures: list[str]


def scalar(connection, sql: str, params: dict[str, object]) -> int:
    return int(connection.execute(text(sql), params).scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--expected", type=int, default=11979)
    parser.add_argument("--version", default="attachment-v2-execution")
    args = parser.parse_args()
    params = {"version": args.version}
    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            questions = scalar(connection, "SELECT count(*) FROM questions q WHERE EXISTS (SELECT 1 FROM question_versions v WHERE v.question_id=q.id AND v.version=:version)", params)
            versions = scalar(connection, "SELECT count(*) FROM question_versions WHERE version=:version", params)
            solutions = scalar(connection, "SELECT count(*) FROM solutions s JOIN question_versions v ON v.id=s.question_version_id WHERE v.version=:version", params)
            explanations = scalar(connection, "SELECT count(*) FROM solutions s JOIN question_versions v ON v.id=s.question_version_id WHERE v.version=:version AND length(btrim(COALESCE(s.explanation,'')))>0", params)
            unique_ids = scalar(connection, "SELECT count(DISTINCT q.external_id) FROM questions q JOIN question_versions v ON v.question_id=q.id WHERE v.version=:version", params)
            published = scalar(connection, "SELECT count(*) FROM questions q JOIN question_versions v ON v.id=q.current_published_version_id WHERE v.version=:version AND v.state='published'::content_state", params)
            runnable = scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND COALESCE((v.structured_content->>'runnable')::boolean,false)", params)
            public_tests = scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND COALESCE((v.structured_content->>'runnable')::boolean,false) AND EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(v.structured_content#>'{mode_specification,tests}','[]'::jsonb)) t WHERE t->>'visibility'='public')", params)
            hidden_tests = scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND COALESCE((v.structured_content->>'runnable')::boolean,false) AND EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(v.structured_content#>'{mode_specification,tests}','[]'::jsonb)) t WHERE t->>'visibility'='hidden')", params)
            search_documents = scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.search_document IS NOT NULL", params)
            subject_rows = connection.execute(text("SELECT COALESCE(v.structured_content->>'subject','unknown'), count(*) FROM question_versions v WHERE v.version=:version GROUP BY 1 ORDER BY 1"), params).all()
            difficulty_rows = connection.execute(text("SELECT v.difficulty, count(*) FROM question_versions v WHERE v.version=:version GROUP BY 1 ORDER BY 1"), params).all()
            seniority_rows = connection.execute(text("SELECT v.expected_seniority, count(*) FROM question_versions v WHERE v.version=:version GROUP BY 1 ORDER BY 1"), params).all()
            index_rows = connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() AND tablename IN ('questions','question_versions','question_skills','skills') ORDER BY indexname")).all()
            # Representative filter/search smoke tests. These intentionally fail if the imported
            # corpus cannot be discovered through the same columns used by the candidate catalog.
            filter_checks = {
                "python": scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.structured_content->>'subject' IN ('Python','Python Coding')", params),
                "sql": scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.structured_content->>'subject' IN ('SQL','SQL Scenario')", params),
                "snowflake": scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.structured_content->>'subject'='Snowflake'", params),
                "data_engineering": scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.structured_content->>'subject'='Data Engineering'", params),
                "ai": scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.structured_content->>'subject'='AI Architecture'", params),
            }
            search_hit = scalar(connection, "SELECT count(*) FROM question_versions v WHERE v.version=:version AND v.search_document @@ websearch_to_tsquery('english','python')", params)
    finally:
        engine.dispose()

    failures: list[str] = []
    for name, value in (("questions", questions), ("versions", versions), ("solutions", solutions), ("explanations", explanations), ("unique_external_ids", unique_ids)):
        if value != args.expected:
            failures.append(f"{name}: expected {args.expected}, found {value}")
    if runnable != public_tests or runnable != hidden_tests:
        failures.append(f"runnable test coverage mismatch: runnable={runnable}, public={public_tests}, hidden={hidden_tests}")
    if search_documents != args.expected:
        failures.append(f"search_document: expected {args.expected}, found {search_documents}")
    if search_hit == 0:
        failures.append("full-text search smoke test returned zero rows")
    for name, value in filter_checks.items():
        if value == 0:
            failures.append(f"filter smoke test returned zero rows: {name}")
    report = Verification(
        expected_questions=args.expected,
        questions=questions,
        versions=versions,
        solutions=solutions,
        explanations=explanations,
        unique_external_ids=unique_ids,
        published=published,
        runnable=runnable,
        runnable_with_public_tests=public_tests,
        runnable_with_hidden_tests=hidden_tests,
        search_documents=search_documents,
        subject_counts={str(key): int(value) for key, value in subject_rows},
        difficulty_counts={str(key): int(value) for key, value in difficulty_rows},
        seniority_counts={str(key): int(value) for key, value in seniority_rows},
        indexes=[str(row[0]) for row in index_rows],
        failures=failures,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
