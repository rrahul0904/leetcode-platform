from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from .knowledge_ingestion import SourceDisposition, slugify


class KnowledgeImportError(ValueError):
    pass


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _corpus_hash(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _objects(value: object, *, label: str) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise KnowledgeImportError(f"{label} must be a list")
    records: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise KnowledgeImportError(f"{label}[{index}] must be an object")
        records.append(cast(dict[str, object], item))
    return records


def _required_string(record: Mapping[str, object], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeImportError(f"{name} is required")
    return value.strip()


def _optional_string(record: Mapping[str, object], name: str) -> str | None:
    value = record.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise KnowledgeImportError(f"{name} must be a string")
    normalized = value.strip()
    return normalized or None


def _disposition(value: object) -> SourceDisposition:
    try:
        return SourceDisposition(str(value))
    except ValueError as exc:
        raise KnowledgeImportError(f"Unsupported source disposition: {value!r}") from exc


def _publication_state(disposition: SourceDisposition) -> tuple[str, str]:
    if disposition is SourceDisposition.HOSTABLE_LICENSED:
        return "draft", "awaiting_technical_review"
    if disposition is SourceDisposition.EXTERNAL_REFERENCE_ONLY:
        return "metadata_only", "rights_metadata_only"
    if disposition is SourceDisposition.REJECTED_PROPRIETARY:
        return "blocked", "rejected_for_rights_risk"
    return "draft", "rights_review_required"


def _uuid(value: object) -> UUID:
    return UUID(str(value))


class KnowledgeBankImporter:
    """Idempotently project normalized source observations into PostgreSQL.

    This importer never publishes content automatically. Even a source marked
    hostable enters the independent technical/editorial review workflow. Rights-
    uncertain and external-reference records remain in the database but cannot
    appear through publication-gated candidate endpoints.
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.counters: Counter[str] = Counter()
        self._source_ids: dict[str, UUID] = {}
        self._file_ids: dict[tuple[str, str, str], UUID] = {}
        self._problem_ids: dict[str, UUID] = {}

    def import_payload(self, payload: Mapping[str, object]) -> dict[str, int]:
        default_disposition = _disposition(
            payload.get("disposition", SourceDisposition.RIGHTS_REVIEW_REQUIRED.value)
        )
        records = {
            "files": _objects(payload.get("files"), label="files"),
            "problems": _objects(payload.get("problems"), label="problems"),
            "solutions": _objects(payload.get("solutions"), label="solutions"),
            "companies": _objects(payload.get("companies"), label="companies"),
            "system_design": _objects(payload.get("system_design"), label="system_design"),
            "resources": _objects(payload.get("resources"), label="resources"),
        }
        source_names = {
            str(item.get("source_name"))
            for values in records.values()
            for item in values
            if isinstance(item.get("source_name"), str) and str(item.get("source_name")).strip()
        }
        if not source_names:
            fallback = str(payload.get("source_name") or "uploaded-corpus")
            source_names.add(fallback)
        for source_name in sorted(source_names):
            self._ensure_source(source_name, default_disposition)

        for item in records["files"]:
            self._upsert_file(item, default_disposition)
        for item in records["problems"]:
            self._upsert_problem(item, default_disposition)
        for item in records["solutions"]:
            self._upsert_solution(item, default_disposition)
        for item in records["companies"]:
            self._upsert_company_observation(item, default_disposition)
        for item in records["system_design"]:
            self._upsert_system_design(item, default_disposition)
        for item in records["resources"]:
            self._upsert_resource(item, default_disposition)
        return dict(sorted(self.counters.items()))

    def _ensure_source(
        self,
        source_name: str,
        disposition: SourceDisposition,
    ) -> UUID:
        cached = self._source_ids.get(source_name)
        if cached is not None:
            return cached
        source_id = _uuid(
            self.connection.execute(
                text(
                    """
                    INSERT INTO knowledge_sources (
                        source_name, original_filename, disposition, source_metadata
                    ) VALUES (
                        :source_name, :original_filename, :disposition,
                        jsonb_build_object('ingestion', 'offline-archive')
                    )
                    ON CONFLICT (source_name) DO UPDATE
                    SET disposition=EXCLUDED.disposition,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "source_name": source_name,
                    "original_filename": (
                        source_name
                        if source_name.casefold().endswith(".zip")
                        else f"{source_name}.zip"
                    ),
                    "disposition": disposition.value,
                },
            ).scalar_one()
        )
        self._source_ids[source_name] = source_id
        self.counters["sources_upserted"] += 1
        return source_id

    def _ensure_file(
        self,
        *,
        source_name: str,
        relative_path: str,
        sha256: str,
        disposition: SourceDisposition,
        byte_count: int = 0,
        suffix: str | None = None,
        classification: str = "synthetic_observation",
        parse_status: str = "available",
        parse_error: str | None = None,
    ) -> UUID:
        key = (source_name, relative_path, sha256)
        cached = self._file_ids.get(key)
        if cached is not None:
            return cached
        source_id = self._ensure_source(source_name, disposition)
        suffix_value = (
            suffix if suffix is not None else PurePosixPath(relative_path).suffix.casefold()
        )
        file_id = _uuid(
            self.connection.execute(
                text(
                    """
                    INSERT INTO knowledge_source_files (
                        source_id, relative_path, sha256, byte_count, suffix,
                        classification, parse_status, parse_error
                    ) VALUES (
                        :source_id, :relative_path, :sha256, :byte_count, :suffix,
                        :classification, :parse_status, :parse_error
                    )
                    ON CONFLICT (source_id, relative_path, sha256) DO UPDATE
                    SET parse_status=EXCLUDED.parse_status,
                        parse_error=EXCLUDED.parse_error
                    RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "relative_path": relative_path,
                    "sha256": sha256,
                    "byte_count": max(0, byte_count),
                    "suffix": suffix_value,
                    "classification": classification,
                    "parse_status": parse_status,
                    "parse_error": parse_error,
                },
            ).scalar_one()
        )
        self._file_ids[key] = file_id
        self.counters["source_files_upserted"] += 1
        return file_id

    def _upsert_file(
        self,
        record: Mapping[str, object],
        disposition: SourceDisposition,
    ) -> UUID:
        source_name = _required_string(record, "source_name")
        relative_path = _required_string(record, "relative_path")
        sha256 = _required_string(record, "sha256")
        byte_count_value = record.get("byte_count", 0)
        byte_count = int(byte_count_value) if isinstance(byte_count_value, (int, float)) else 0
        return self._ensure_file(
            source_name=source_name,
            relative_path=relative_path,
            sha256=sha256,
            disposition=disposition,
            byte_count=byte_count,
            suffix=str(record.get("suffix") or PurePosixPath(relative_path).suffix.casefold()),
            classification=str(record.get("classification") or "unsupported"),
            parse_status=str(record.get("parse_status") or "available"),
            parse_error=_optional_string(record, "error"),
        )

    def _problem_id(self, canonical_key: str) -> UUID:
        cached = self._problem_ids.get(canonical_key)
        if cached is not None:
            return cached
        value = self.connection.execute(
            text("SELECT id FROM knowledge_problems WHERE canonical_key=:canonical_key"),
            {"canonical_key": canonical_key},
        ).scalar_one_or_none()
        if value is None:
            raise KnowledgeImportError(f"Solution references unknown problem {canonical_key}")
        problem_id = _uuid(value)
        self._problem_ids[canonical_key] = problem_id
        return problem_id

    def _upsert_problem(
        self,
        record: Mapping[str, object],
        default_disposition: SourceDisposition,
    ) -> UUID:
        canonical_key = _required_string(record, "canonical_key")
        title = _required_string(record, "title")
        slug = _required_string(record, "slug")
        source_name = _required_string(record, "source_name")
        source_path = _required_string(record, "source_path")
        source_hash = _required_string(record, "source_hash")
        disposition = _disposition(record.get("disposition", default_disposition.value))
        publication_status, review_status = _publication_state(disposition)
        description = _optional_string(record, "description")
        problem_id = _uuid(
            self.connection.execute(
                text(
                    """
                    INSERT INTO knowledge_problems (
                        canonical_key, external_id, title, slug, summary, description,
                        difficulty, source_url, publication_status, review_status,
                        primary_language, source_metadata
                    ) VALUES (
                        :canonical_key, :external_id, :title, :slug,
                        left(:description, 500), :description, :difficulty, :source_url,
                        :publication_status, :review_status, NULL,
                        jsonb_build_object('disposition', :disposition)
                    )
                    ON CONFLICT (canonical_key) DO UPDATE
                    SET title=EXCLUDED.title,
                        slug=CASE
                            WHEN knowledge_problems.slug=EXCLUDED.slug THEN EXCLUDED.slug
                            ELSE knowledge_problems.slug
                        END,
                        external_id=COALESCE(knowledge_problems.external_id, EXCLUDED.external_id),
                        description=CASE
                            WHEN length(COALESCE(EXCLUDED.description, ''))
                                 > length(COALESCE(knowledge_problems.description, ''))
                            THEN EXCLUDED.description
                            ELSE knowledge_problems.description
                        END,
                        difficulty=COALESCE(knowledge_problems.difficulty, EXCLUDED.difficulty),
                        source_url=COALESCE(knowledge_problems.source_url, EXCLUDED.source_url),
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "canonical_key": canonical_key,
                    "external_id": _optional_string(record, "external_id"),
                    "title": title,
                    "slug": slug,
                    "description": description,
                    "difficulty": _optional_string(record, "difficulty"),
                    "source_url": _optional_string(record, "source_url"),
                    "publication_status": publication_status,
                    "review_status": review_status,
                    "disposition": disposition.value,
                },
            ).scalar_one()
        )
        self._problem_ids[canonical_key] = problem_id
        source_file_id = self._ensure_file(
            source_name=source_name,
            relative_path=source_path,
            sha256=source_hash,
            disposition=disposition,
        )
        self.connection.execute(
            text(
                """
                INSERT INTO knowledge_problem_sources (
                    problem_id, source_file_id, source_hash, source_path, disposition
                ) VALUES (
                    :problem_id, :source_file_id, :source_hash, :source_path, :disposition
                )
                ON CONFLICT (problem_id, source_file_id) DO UPDATE
                SET source_hash=EXCLUDED.source_hash,
                    disposition=EXCLUDED.disposition,
                    observed_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "problem_id": problem_id,
                "source_file_id": source_file_id,
                "source_hash": source_hash,
                "source_path": source_path,
                "disposition": disposition.value,
            },
        )
        topics = record.get("topics", [])
        if isinstance(topics, (list, tuple)):
            for raw_topic in topics:
                topic_slug = slugify(str(raw_topic))
                if not topic_slug:
                    continue
                topic_id = _uuid(
                    self.connection.execute(
                        text(
                            """
                            INSERT INTO knowledge_topics (slug, name, category)
                            VALUES (:slug, :name, 'topic')
                            ON CONFLICT (slug) DO UPDATE
                            SET name=EXCLUDED.name, updated_at=CURRENT_TIMESTAMP
                            RETURNING id
                            """
                        ),
                        {
                            "slug": topic_slug,
                            "name": topic_slug.replace("-", " ").title(),
                        },
                    ).scalar_one()
                )
                self.connection.execute(
                    text(
                        """
                        INSERT INTO knowledge_problem_topics (problem_id, topic_id, confidence, source)
                        VALUES (:problem_id, :topic_id, 1.0, 'imported')
                        ON CONFLICT (problem_id, topic_id) DO NOTHING
                        """
                    ),
                    {"problem_id": problem_id, "topic_id": topic_id},
                )
        self.counters["problems_upserted"] += 1
        return problem_id

    def _upsert_solution(
        self,
        record: Mapping[str, object],
        default_disposition: SourceDisposition,
    ) -> None:
        canonical_key = _required_string(record, "canonical_key")
        problem_id = self._problem_id(canonical_key)
        source_name = _required_string(record, "source_name")
        source_path = _required_string(record, "source_path")
        source_hash = _required_string(record, "source_hash")
        language = _required_string(record, "language").casefold()
        disposition = _disposition(record.get("disposition", default_disposition.value))
        _publication_status, review_status = _publication_state(disposition)
        source_file_id = self._ensure_file(
            source_name=source_name,
            relative_path=source_path,
            sha256=source_hash,
            disposition=disposition,
            classification="source_code",
        )
        explanation = _optional_string(record, "explanation")
        approach_slug = "imported-reference"
        approach_id = _uuid(
            self.connection.execute(
                text(
                    """
                    INSERT INTO knowledge_solution_approaches (
                        problem_id, name, slug, explanation,
                        time_complexity, space_complexity, sequence_number
                    ) VALUES (
                        :problem_id, 'Imported reference approaches', :slug, :explanation,
                        :time_complexity, :space_complexity, 1
                    )
                    ON CONFLICT (problem_id, slug) DO UPDATE
                    SET explanation=CASE
                            WHEN length(COALESCE(EXCLUDED.explanation, ''))
                                 > length(COALESCE(knowledge_solution_approaches.explanation, ''))
                            THEN EXCLUDED.explanation
                            ELSE knowledge_solution_approaches.explanation
                        END,
                        time_complexity=COALESCE(
                            knowledge_solution_approaches.time_complexity,
                            EXCLUDED.time_complexity
                        ),
                        space_complexity=COALESCE(
                            knowledge_solution_approaches.space_complexity,
                            EXCLUDED.space_complexity
                        ),
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "problem_id": problem_id,
                    "slug": approach_slug,
                    "explanation": explanation,
                    "time_complexity": _optional_string(record, "time_complexity"),
                    "space_complexity": _optional_string(record, "space_complexity"),
                },
            ).scalar_one()
        )
        executable = (
            language in {"python", "javascript", "sql"}
            and disposition is SourceDisposition.HOSTABLE_LICENSED
        )
        self.connection.execute(
            text(
                """
                INSERT INTO knowledge_solutions (
                    approach_id, source_file_id, language, runtime, source_code,
                    explanation, source_hash, is_executable, review_status
                ) VALUES (
                    :approach_id, :source_file_id, :language, :runtime, :source_code,
                    :explanation, :source_hash, :is_executable, :review_status
                )
                ON CONFLICT (approach_id, language, source_hash) DO UPDATE
                SET source_code=EXCLUDED.source_code,
                    explanation=COALESCE(EXCLUDED.explanation, knowledge_solutions.explanation),
                    is_executable=EXCLUDED.is_executable,
                    review_status=EXCLUDED.review_status,
                    updated_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "approach_id": approach_id,
                "source_file_id": source_file_id,
                "language": language,
                "runtime": {
                    "python": "python3.13",
                    "javascript": "node22",
                    "sql": "postgresql18",
                }.get(language),
                "source_code": _required_string(record, "source_code"),
                "explanation": explanation,
                "source_hash": source_hash,
                "is_executable": executable,
                "review_status": review_status,
            },
        )
        self.connection.execute(
            text(
                """
                UPDATE knowledge_problems
                SET primary_language=COALESCE(primary_language, :language),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:problem_id
                """
            ),
            {"problem_id": problem_id, "language": language},
        )
        self.counters["solutions_upserted"] += 1

    def _upsert_company_observation(
        self,
        record: Mapping[str, object],
        default_disposition: SourceDisposition,
    ) -> None:
        canonical_key = _required_string(record, "canonical_key")
        problem_id = self._problem_ids.get(canonical_key)
        if problem_id is None:
            # Company archives often contain the only observation for a problem.
            problem_id = self._upsert_problem(
                {
                    "canonical_key": canonical_key,
                    "external_id": record.get("external_id"),
                    "title": _required_string(record, "title"),
                    "slug": slugify(_required_string(record, "title")),
                    "description": None,
                    "difficulty": record.get("difficulty"),
                    "source_url": record.get("problem_url"),
                    "topics": record.get("topics", []),
                    "source_name": record.get("source_name"),
                    "source_path": record.get("source_path"),
                    "source_hash": record.get("source_hash"),
                    "disposition": SourceDisposition.EXTERNAL_REFERENCE_ONLY.value,
                },
                SourceDisposition.EXTERNAL_REFERENCE_ONLY,
            )
        source_name = _required_string(record, "source_name")
        source_path = _required_string(record, "source_path")
        source_hash = _required_string(record, "source_hash")
        source_file_id = self._ensure_file(
            source_name=source_name,
            relative_path=source_path,
            sha256=source_hash,
            disposition=default_disposition,
            classification="structured_text",
        )
        company_name = _required_string(record, "company")
        company_slug = slugify(company_name)
        company_id = _uuid(
            self.connection.execute(
                text(
                    """
                    INSERT INTO knowledge_companies (slug, name)
                    VALUES (:slug, :name)
                    ON CONFLICT (slug) DO UPDATE
                    SET name=EXCLUDED.name, updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {"slug": company_slug, "name": company_name},
            ).scalar_one()
        )
        self.connection.execute(
            text(
                """
                INSERT INTO knowledge_company_observations (
                    problem_id, company_id, source_file_id, observation_window,
                    frequency, acceptance_rate, difficulty, source_hash
                ) VALUES (
                    :problem_id, :company_id, :source_file_id, :observation_window,
                    :frequency, :acceptance_rate, :difficulty, :source_hash
                )
                ON CONFLICT (
                    problem_id, company_id, observation_window, source_hash
                ) DO UPDATE
                SET frequency=EXCLUDED.frequency,
                    acceptance_rate=EXCLUDED.acceptance_rate,
                    difficulty=EXCLUDED.difficulty,
                    observed_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "problem_id": problem_id,
                "company_id": company_id,
                "source_file_id": source_file_id,
                "observation_window": _optional_string(record, "observation_window"),
                "frequency": record.get("frequency"),
                "acceptance_rate": record.get("acceptance_rate"),
                "difficulty": _optional_string(record, "difficulty"),
                "source_hash": source_hash,
            },
        )
        self.counters["company_observations_upserted"] += 1

    def _upsert_system_design(
        self,
        record: Mapping[str, object],
        default_disposition: SourceDisposition,
    ) -> None:
        source_name = _required_string(record, "source_name")
        source_path = _required_string(record, "source_path")
        source_hash = _required_string(record, "source_hash")
        disposition = _disposition(record.get("disposition", default_disposition.value))
        publication_status, review_status = _publication_state(disposition)
        source_file_id = self._ensure_file(
            source_name=source_name,
            relative_path=source_path,
            sha256=source_hash,
            disposition=disposition,
            classification="structured_text",
        )
        self.connection.execute(
            text(
                """
                INSERT INTO knowledge_system_design_articles (
                    source_file_id, slug, title, body, headings, image_paths,
                    source_hash, publication_status, review_status
                ) VALUES (
                    :source_file_id, :slug, :title, :body,
                    CAST(:headings AS jsonb), CAST(:image_paths AS jsonb),
                    :source_hash, :publication_status, :review_status
                )
                ON CONFLICT (slug) DO UPDATE
                SET title=EXCLUDED.title,
                    body=EXCLUDED.body,
                    headings=EXCLUDED.headings,
                    image_paths=EXCLUDED.image_paths,
                    source_hash=EXCLUDED.source_hash,
                    review_status=EXCLUDED.review_status,
                    updated_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "source_file_id": source_file_id,
                "slug": _required_string(record, "slug"),
                "title": _required_string(record, "title"),
                "body": _required_string(record, "body"),
                "headings": json.dumps(record.get("headings", [])),
                "image_paths": json.dumps(record.get("image_paths", [])),
                "source_hash": source_hash,
                "publication_status": publication_status,
                "review_status": review_status,
            },
        )
        self.counters["system_design_articles_upserted"] += 1

    def _upsert_resource(
        self,
        record: Mapping[str, object],
        default_disposition: SourceDisposition,
    ) -> None:
        source_name = _required_string(record, "source_name")
        source_path = _required_string(record, "source_path")
        source_hash = _required_string(record, "source_hash")
        disposition = _disposition(record.get("disposition", default_disposition.value))
        publication_status, review_status = _publication_state(disposition)
        source_file_id = self._ensure_file(
            source_name=source_name,
            relative_path=source_path,
            sha256=source_hash,
            disposition=disposition,
        )
        self.connection.execute(
            text(
                """
                INSERT INTO knowledge_learning_resources (
                    source_file_id, slug, title, category, language, body,
                    source_hash, publication_status, review_status
                ) VALUES (
                    :source_file_id, :slug, :title, :category, :language, :body,
                    :source_hash, :publication_status, :review_status
                )
                ON CONFLICT (slug) DO UPDATE
                SET title=EXCLUDED.title,
                    category=EXCLUDED.category,
                    language=EXCLUDED.language,
                    body=EXCLUDED.body,
                    source_hash=EXCLUDED.source_hash,
                    review_status=EXCLUDED.review_status,
                    updated_at=CURRENT_TIMESTAMP
                """
            ),
            {
                "source_file_id": source_file_id,
                "slug": _required_string(record, "slug"),
                "title": _required_string(record, "title"),
                "category": _required_string(record, "category"),
                "language": _optional_string(record, "language"),
                "body": _required_string(record, "body"),
                "source_hash": source_hash,
                "publication_status": publication_status,
                "review_status": review_status,
            },
        )
        self.counters["learning_resources_upserted"] += 1


def import_knowledge_payload(
    engine: Engine,
    payload: Mapping[str, object],
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    corpus_sha256 = _corpus_hash(payload)
    source_name = str(payload.get("source_name") or "merged-upload-corpus")
    disposition = _disposition(
        payload.get("disposition", SourceDisposition.RIGHTS_REVIEW_REQUIRED.value)
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            importer = KnowledgeBankImporter(connection)
            source_id = importer._ensure_source(source_name, disposition)
            previous = (
                connection.execute(
                    text(
                        """
                    SELECT id, counters
                    FROM knowledge_import_runs
                    WHERE source_id=:source_id AND corpus_sha256=:corpus_sha256
                      AND status='completed'
                    """
                    ),
                    {"source_id": source_id, "corpus_sha256": corpus_sha256},
                )
                .mappings()
                .one_or_none()
            )
            if previous is not None and not dry_run:
                transaction.rollback()
                return {
                    "import_id": str(previous["id"]),
                    "status": "already_imported",
                    "corpus_sha256": corpus_sha256,
                    "counters": previous["counters"],
                }
            import_id = _uuid(
                connection.execute(
                    text(
                        """
                        INSERT INTO knowledge_import_runs (
                            source_id, corpus_sha256, status, dry_run
                        ) VALUES (
                            :source_id, :corpus_sha256, 'running', :dry_run
                        )
                        ON CONFLICT (source_id, corpus_sha256) DO UPDATE
                        SET status='running', dry_run=EXCLUDED.dry_run,
                            started_at=CURRENT_TIMESTAMP, completed_at=NULL
                        RETURNING id
                        """
                    ),
                    {
                        "source_id": source_id,
                        "corpus_sha256": corpus_sha256,
                        "dry_run": dry_run,
                    },
                ).scalar_one()
            )
            counters = importer.import_payload(payload)
            connection.execute(
                text(
                    """
                    UPDATE knowledge_import_runs
                    SET status='completed', counters=CAST(:counters AS jsonb),
                        completed_at=CURRENT_TIMESTAMP
                    WHERE id=:import_id
                    """
                ),
                {"import_id": import_id, "counters": json.dumps(counters)},
            )
            result: dict[str, object] = {
                "import_id": str(import_id),
                "status": "validated" if dry_run else "completed",
                "corpus_sha256": corpus_sha256,
                "counters": counters,
            }
            if dry_run:
                transaction.rollback()
            else:
                transaction.commit()
            return result
        except Exception:
            transaction.rollback()
            raise


def import_knowledge_file(
    engine: Engine,
    path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KnowledgeImportError(f"Knowledge corpus is unavailable or invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise KnowledgeImportError("Knowledge corpus root must be an object")
    return import_knowledge_payload(
        engine,
        cast(dict[str, object], payload),
        dry_run=dry_run,
    )
