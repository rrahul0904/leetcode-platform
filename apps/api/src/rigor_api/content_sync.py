from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError
from rigor_question_schema import QuestionPackage, SolutionPackage
from rigor_question_schema.models import PythonSpecification, SqlSpecification
from sqlalchemy import Connection, Engine, text


@dataclass(frozen=True)
class LoadedContentPackage:
    directory: Path
    question: QuestionPackage
    solution: SolutionPackage
    content_hash: str


@dataclass(frozen=True)
class PackageSyncResult:
    question_id: str
    version: str
    status: Literal["valid", "invalid", "inserted", "updated", "unchanged", "rolled_back"]
    content_hash: str | None
    findings: list[str]


@dataclass(frozen=True)
class ContentSyncReport:
    mode: str
    started_at: str
    completed_at: str
    source_revision: str
    discovered: int
    valid: int
    invalid: int
    inserted: int
    updated: int
    unchanged: int
    rolled_back: int
    results: list[PackageSyncResult]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2) + "\n"


def discover_package_directories(content_root: Path) -> list[Path]:
    return sorted(path.parent for path in (content_root / "questions").glob("**/question.json"))


def load_manifest_ids(content_root: Path) -> set[str]:
    manifest = json.loads((content_root / "question-bank-manifest.json").read_text())
    return {str(question["id"]) for question in manifest["questions"]}


def load_package(directory: Path) -> LoadedContentPackage:
    question_path = directory / "question.json"
    sidecars = {
        "solution": directory / "solution.json",
        "rubric": directory / "rubric.json",
        "metadata": directory / "metadata.json",
        "public_tests": directory / "tests" / "public.json",
        "hidden_tests": directory / "tests" / "hidden.json",
    }
    missing = [name for name, path in sidecars.items() if not path.exists()]
    if missing:
        raise ValueError(f"missing sidecars: {', '.join(missing)}")
    raw_question = json.loads(question_path.read_text(encoding="utf-8"))
    raw_solution = json.loads(sidecars["solution"].read_text(encoding="utf-8"))
    raw_metadata = json.loads(sidecars["metadata"].read_text(encoding="utf-8"))
    raw_question["evaluation_rubric"] = json.loads(sidecars["rubric"].read_text(encoding="utf-8"))
    raw_question.update(raw_metadata)
    mode = raw_question["mode_specification"]
    if "runtime" in mode or "dialect" in mode:
        mode["tests"] = [
            *json.loads(sidecars["public_tests"].read_text(encoding="utf-8")),
            *json.loads(sidecars["hidden_tests"].read_text(encoding="utf-8")),
        ]
    question = QuestionPackage.model_validate(raw_question)
    solution = SolutionPackage.model_validate(raw_solution)
    digest = hashlib.sha256(question_path.read_bytes()).hexdigest()
    expected_hash = f"sha256:{digest}"
    if question.provenance.content_hash != expected_hash:
        raise ValueError("provenance content hash does not match question.json")
    if solution.source_content_hash != expected_hash:
        raise ValueError("solution source hash does not match question.json")
    if solution.question_id != question.id or solution.question_version != question.version:
        raise ValueError("solution identity or version does not match the question")
    return LoadedContentPackage(directory, question, solution, digest)


def validate_package(
    package: LoadedContentPackage,
    *,
    manifest_ids: set[str],
    authored_ids: set[str],
) -> list[str]:
    findings: list[str] = []
    question = package.question
    if question.id not in manifest_ids:
        findings.append("question ID is absent from the approved manifest")
    unknown_related = sorted(set(question.related_question_ids) - manifest_ids)
    if unknown_related:
        findings.append(f"unknown related IDs: {', '.join(unknown_related)}")
    missing_authored = sorted(set(question.related_question_ids) - authored_ids)
    if missing_authored:
        findings.append(f"related packages are not authored: {', '.join(missing_authored)}")
    mode_specification = question.mode_specification
    if isinstance(mode_specification, (PythonSpecification, SqlSpecification)):
        test_ids = [test.id for test in mode_specification.tests]
        if len(test_ids) != len(set(test_ids)):
            findings.append("test IDs must be unique")
        public_count = sum(test.visibility == "public" for test in mode_specification.tests)
        hidden_count = sum(test.visibility == "hidden" for test in mode_specification.tests)
        if public_count == 0 or hidden_count == 0:
            findings.append("at least one public and one hidden test are required")
    reference_test = package.directory / "test_reference.py"
    if reference_test.exists():
        execution = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(reference_test)],
            cwd=package.directory.parents[3],
            capture_output=True,
            text=True,
            check=False,
        )
        if execution.returncode != 0:
            findings.append("reference tests failed")
    elif question.primary_track in {"python-engineering", "sql-analytics"}:
        findings.append("executable track is missing a reference test harness")
    return findings


def validate_all(
    content_root: Path, selected_ids: set[str] | None = None
) -> list[PackageSyncResult]:
    directories = discover_package_directories(content_root)
    authored_ids = {directory.name for directory in directories}
    manifest_ids = load_manifest_ids(content_root)
    loaded: list[LoadedContentPackage] = []
    results: list[PackageSyncResult] = []
    for directory in directories:
        if selected_ids and directory.name not in selected_ids:
            continue
        try:
            package = load_package(directory)
        except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            results.append(
                PackageSyncResult(directory.name, "unknown", "invalid", None, [str(exc)])
            )
            continue
        loaded.append(package)
    duplicate_titles: dict[str, list[str]] = {}
    for package in loaded:
        duplicate_titles.setdefault(package.question.title.casefold(), []).append(
            package.question.id
        )
    duplicate_ids = {
        question_id for ids in duplicate_titles.values() if len(ids) > 1 for question_id in ids
    }
    for package in loaded:
        findings = validate_package(
            package,
            manifest_ids=manifest_ids,
            authored_ids=authored_ids,
        )
        if package.question.id in duplicate_ids:
            findings.append("authored package title is an exact duplicate")
        results.append(
            PackageSyncResult(
                package.question.id,
                package.question.version,
                "invalid" if findings else "valid",
                package.content_hash,
                findings,
            )
        )
    return sorted(results, key=lambda item: item.question_id)


class ContentSynchronizer:
    def __init__(self, engine: Engine, content_root: Path, source_revision: str) -> None:
        self.engine = engine
        self.content_root = content_root
        self.source_revision = source_revision[:64]

    def run(
        self,
        *,
        mode: Literal["validate", "dry-run", "sync"],
        selected_ids: set[str] | None = None,
    ) -> ContentSyncReport:
        started = datetime.now(UTC)
        validation = validate_all(self.content_root, selected_ids)
        results = validation
        if mode == "sync":
            valid_ids = {result.question_id for result in validation if result.status == "valid"}
            package_by_id = {
                directory.name: load_package(directory)
                for directory in discover_package_directories(self.content_root)
                if directory.name in valid_ids
            }
            results = [
                self._synchronize_package(package_by_id[result.question_id])
                if result.status == "valid"
                else result
                for result in validation
            ]
        completed = datetime.now(UTC)
        return ContentSyncReport(
            mode=mode,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            source_revision=self.source_revision,
            discovered=len(validation),
            valid=sum(result.status != "invalid" for result in results),
            invalid=sum(result.status == "invalid" for result in results),
            inserted=sum(result.status == "inserted" for result in results),
            updated=sum(result.status == "updated" for result in results),
            unchanged=sum(result.status == "unchanged" for result in results),
            rolled_back=sum(result.status == "rolled_back" for result in results),
            results=results,
        )

    def rollback(self, question_id: str, target_version: str) -> ContentSyncReport:
        started = datetime.now(UTC)
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    SELECT q.id AS question_id, q.current_published_version_id,
                           v.id AS version_id, v.version, v.content_hash, v.source_revision,
                           EXISTS (
                               SELECT 1 FROM publication_events pe
                               WHERE pe.question_version_id=v.id
                           ) AS was_published
                    FROM questions q JOIN question_versions v ON v.question_id=q.id
                    WHERE q.external_id=:question_id AND v.version=:version
                    FOR UPDATE OF q, v
                    """
                    ),
                    {"question_id": question_id, "version": target_version},
                )
                .mappings()
                .one_or_none()
            )
            if row is None or not row["was_published"]:
                result = PackageSyncResult(
                    question_id,
                    target_version,
                    "invalid",
                    None,
                    ["rollback target is not a previously published version"],
                )
            elif row["current_published_version_id"] == row["version_id"]:
                result = PackageSyncResult(
                    question_id, target_version, "unchanged", row["content_hash"], []
                )
            else:
                actor_id = connection.execute(
                    text(
                        """
                        INSERT INTO users (
                            identity_subject, email, display_name, email_verified
                        ) VALUES (
                            'system:content-sync', 'content-sync@rigor.test',
                            'Content Synchronizer', true
                        )
                        ON CONFLICT (identity_subject) DO UPDATE
                        SET display_name=EXCLUDED.display_name RETURNING id
                        """
                    )
                ).scalar_one()
                current = row["current_published_version_id"]
                if current is not None:
                    connection.execute(
                        text(
                            "UPDATE question_versions SET state='deprecated'::content_state, "
                            "updated_at=CURRENT_TIMESTAMP WHERE id=:version_id"
                        ),
                        {"version_id": current},
                    )
                connection.execute(
                    text(
                        "UPDATE question_versions SET state='published'::content_state, "
                        "updated_at=CURRENT_TIMESTAMP WHERE id=:version_id"
                    ),
                    {"version_id": row["version_id"]},
                )
                connection.execute(
                    text(
                        "UPDATE questions SET current_published_version_id=:version_id, "
                        "archived_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=:question_id"
                    ),
                    {"version_id": row["version_id"], "question_id": row["question_id"]},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO audit_events (
                            actor_user_id, action, resource_type, resource_id,
                            details, correlation_id
                        ) VALUES (
                            :actor_id, 'content.rollback', 'question_version', :resource_id,
                            CAST(:details AS jsonb), 'content-sync-rollback'
                        )
                        """
                    ),
                    {
                        "actor_id": actor_id,
                        "resource_id": str(row["version_id"]),
                        "details": json.dumps(
                            {
                                "question_id": question_id,
                                "target_version": target_version,
                                "replaced_version_id": str(current) if current else None,
                                "source_revision": self.source_revision,
                            }
                        ),
                    },
                )
                result = PackageSyncResult(
                    question_id, target_version, "rolled_back", row["content_hash"], []
                )
        completed = datetime.now(UTC)
        return ContentSyncReport(
            mode="rollback",
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            source_revision=self.source_revision,
            discovered=1,
            valid=int(result.status != "invalid"),
            invalid=int(result.status == "invalid"),
            inserted=0,
            updated=0,
            unchanged=int(result.status == "unchanged"),
            rolled_back=int(result.status == "rolled_back"),
            results=[result],
        )

    def _synchronize_package(self, package: LoadedContentPackage) -> PackageSyncResult:
        question = package.question
        with self.engine.begin() as connection:
            track_id = connection.execute(
                text("SELECT id FROM question_tracks WHERE slug = :slug"),
                {"slug": question.primary_track},
            ).scalar_one_or_none()
            if track_id is None:
                return PackageSyncResult(
                    question.id,
                    question.version,
                    "invalid",
                    package.content_hash,
                    ["primary track is not seeded"],
                )
            question_id = connection.execute(
                text(
                    """
                    INSERT INTO questions (external_id, slug, primary_track_id)
                    VALUES (:external_id, :slug, :track_id)
                    ON CONFLICT (external_id) DO UPDATE SET
                        slug = EXCLUDED.slug,
                        primary_track_id = EXCLUDED.primary_track_id,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {"external_id": question.id, "slug": question.slug, "track_id": track_id},
            ).scalar_one()
            existing = (
                connection.execute(
                    text(
                        """
                        SELECT id, state::text AS state, content_hash
                        FROM question_versions
                        WHERE question_id = :question_id AND version = :version
                        """
                    ),
                    {"question_id": question_id, "version": question.version},
                )
                .mappings()
                .one_or_none()
            )
            self._replace_question_competencies(connection, package, UUID(str(question_id)))
            if existing and existing["content_hash"] == package.content_hash:
                return PackageSyncResult(
                    question.id, question.version, "unchanged", package.content_hash, []
                )
            if existing and existing["state"] in {"approved", "published"}:
                return PackageSyncResult(
                    question.id,
                    question.version,
                    "invalid",
                    package.content_hash,
                    ["approved or published versions are immutable; create a new version"],
                )
            version_id = self._upsert_version(
                connection, package, UUID(str(question_id)), dict(existing) if existing else None
            )
            self._replace_sidecars(connection, package, version_id)
            self._record_sync_audit(connection, question.id, version_id)
            return PackageSyncResult(
                question.id,
                question.version,
                "updated" if existing else "inserted",
                package.content_hash,
                [],
            )

    @staticmethod
    def _replace_question_competencies(
        connection: Connection, package: LoadedContentPackage, question_id: UUID
    ) -> None:
        connection.execute(
            text("DELETE FROM question_competencies WHERE question_id=:question_id"),
            {"question_id": question_id},
        )
        competency_slugs = list(
            dict.fromkeys([package.question.primary_track, *package.question.secondary_skills])
        )
        competency_rows = connection.execute(
            text("SELECT id, slug FROM competencies WHERE slug = ANY(:slugs)"),
            {"slugs": competency_slugs},
        ).mappings()
        for competency in competency_rows:
            connection.execute(
                text(
                    """
                    INSERT INTO question_competencies (
                        question_id, competency_id, is_primary, confidence
                    ) VALUES (:question_id, :competency_id, :is_primary, 1)
                    """
                ),
                {
                    "question_id": question_id,
                    "competency_id": competency["id"],
                    "is_primary": competency["slug"] == package.question.primary_track,
                },
            )

    def _record_sync_audit(
        self, connection: Connection, external_id: str, version_id: UUID
    ) -> None:
        actor_id = connection.execute(
            text(
                """
                INSERT INTO users (
                    identity_subject, email, display_name, email_verified
                ) VALUES (
                    'system:content-sync', 'content-sync@rigor.test',
                    'Content Synchronizer', true
                )
                ON CONFLICT (identity_subject) DO UPDATE
                SET display_name=EXCLUDED.display_name RETURNING id
                """
            )
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO audit_events (
                    actor_user_id, action, resource_type, resource_id,
                    details, correlation_id
                ) VALUES (
                    :actor_id, 'content.synchronized', 'question_version', :resource_id,
                    CAST(:details AS jsonb), 'content-sync'
                )
                """
            ),
            {
                "actor_id": actor_id,
                "resource_id": str(version_id),
                "details": json.dumps(
                    {"external_id": external_id, "source_revision": self.source_revision}
                ),
            },
        )

    def _upsert_version(
        self,
        connection: Connection,
        package: LoadedContentPackage,
        question_id: UUID,
        existing: dict[str, Any] | None,
    ) -> UUID:
        question = package.question
        structured = question.model_dump(mode="json")
        values = {
            "question_id": question_id,
            "version": question.version,
            "title": question.title,
            "problem_statement": question.problem_statement,
            "expected_seniority": question.expected_seniority,
            "difficulty": question.difficulty.value,
            "conceptual": question.difficulty_dimensions.conceptual,
            "implementation": question.difficulty_dimensions.implementation,
            "scale": question.difficulty_dimensions.scale,
            "ambiguity": question.difficulty_dimensions.ambiguity,
            "prerequisite_depth": question.difficulty_dimensions.prerequisite_depth,
            "duration": question.estimated_duration_minutes,
            "state": "awaiting_technical_review",
            "structured": json.dumps(structured),
            "content_hash": package.content_hash,
            "source_revision": self.source_revision,
        }
        if existing:
            values["version_id"] = existing["id"]
            connection.execute(
                text(
                    """
                    UPDATE question_versions SET
                        title=:title, problem_statement=:problem_statement,
                        expected_seniority=:expected_seniority, difficulty=:difficulty,
                        conceptual_difficulty=:conceptual,
                        implementation_difficulty=:implementation, scale=:scale,
                        ambiguity=:ambiguity, prerequisite_depth=:prerequisite_depth,
                        duration_minutes=:duration, state=CAST(:state AS content_state),
                        structured_content=CAST(:structured AS jsonb),
                        content_hash=:content_hash, source_revision=:source_revision,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=:version_id
                    """
                ),
                values,
            )
            return UUID(str(existing["id"]))
        return UUID(
            str(
                connection.execute(
                    text(
                        """
                        INSERT INTO question_versions (
                            question_id, version, title, problem_statement, expected_seniority,
                            difficulty, conceptual_difficulty, implementation_difficulty,
                            scale, ambiguity, prerequisite_depth, duration_minutes, state,
                            structured_content, content_hash, source_revision
                        ) VALUES (
                            :question_id, :version, :title, :problem_statement,
                            :expected_seniority, :difficulty, :conceptual, :implementation,
                            :scale, :ambiguity, :prerequisite_depth, :duration,
                            CAST(:state AS content_state), CAST(:structured AS jsonb),
                            :content_hash, :source_revision
                        ) RETURNING id
                        """
                    ),
                    values,
                ).scalar_one()
            )
        )

    def _replace_sidecars(
        self, connection: Connection, package: LoadedContentPackage, version_id: UUID
    ) -> None:
        question, solution = package.question, package.solution
        for table in (
            "question_skills",
            "question_company_tags",
            "learning_objectives",
            "solutions",
            "rubrics",
            "provenance_records",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE question_version_id = :version_id"),
                {"version_id": version_id},
            )
        for skill in question.secondary_skills:
            skill_id = connection.execute(
                text(
                    """
                    INSERT INTO skills (slug, name, category)
                    VALUES (:slug, :name, :category)
                    ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                    RETURNING id
                    """
                ),
                {
                    "slug": skill,
                    "name": skill.replace("-", " ").title(),
                    "category": question.primary_track,
                },
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO question_skills (question_version_id, skill_id) "
                    "VALUES (:version_id, :skill_id)"
                ),
                {"version_id": version_id, "skill_id": skill_id},
            )
        for tag in question.company_style_tags:
            tag_id = connection.execute(
                text(
                    """
                    INSERT INTO company_style_tags (slug, name, independence_disclaimer)
                    VALUES (
                        :slug, :name,
                        'Independent original curriculum; ' || 'no employer affiliation.'
                    )
                    ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"slug": tag.slug, "name": tag.slug.replace("-", " ").title()},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO question_company_tags (
                        question_version_id, company_style_tag_id,
                        relevance_rationale, public_theme_sources
                    ) VALUES (:version_id, :tag_id, :rationale, CAST(:sources AS jsonb))
                    """
                ),
                {
                    "version_id": version_id,
                    "tag_id": tag_id,
                    "rationale": tag.relevance_rationale,
                    "sources": json.dumps(tag.public_theme_sources),
                },
            )
        for ordinal, objective in enumerate(question.learning_objectives, start=1):
            connection.execute(
                text(
                    """
                    INSERT INTO learning_objectives (question_version_id, ordinal, objective)
                    VALUES (:version_id, :ordinal, :objective)
                    """
                ),
                {"version_id": version_id, "ordinal": ordinal, "objective": objective},
            )
        connection.execute(
            text(
                """
                INSERT INTO solutions (
                    question_version_id, reference_solution, explanation,
                    trade_off_analysis, source_content_hash
                ) VALUES (
                    :version_id, :reference_solution, :explanation,
                    CAST(:trade_offs AS jsonb), :source_hash
                )
                """
            ),
            {
                "version_id": version_id,
                "reference_solution": solution.reference_solution,
                "explanation": solution.explanation,
                "trade_offs": json.dumps(solution.trade_off_analysis),
                "source_hash": package.content_hash,
            },
        )
        rubric_id = connection.execute(
            text(
                """
                INSERT INTO rubrics (question_version_id, score_bands)
                VALUES (:version_id, CAST(:score_bands AS jsonb)) RETURNING id
                """
            ),
            {
                "version_id": version_id,
                "score_bands": json.dumps(question.evaluation_rubric.score_bands),
            },
        ).scalar_one()
        for ordinal, dimension in enumerate(question.evaluation_rubric.dimensions, start=1):
            connection.execute(
                text(
                    """
                    INSERT INTO rubric_dimensions (
                        rubric_id, name, description, weight, ordinal, indicators
                    ) VALUES (
                        :rubric_id, :name, :description, :weight, :ordinal,
                        CAST(:indicators AS jsonb)
                    )
                    """
                ),
                {
                    "rubric_id": rubric_id,
                    "name": dimension.name,
                    "description": dimension.description,
                    "weight": dimension.weight,
                    "ordinal": ordinal,
                    "indicators": json.dumps(
                        {
                            "evidence_required": dimension.evidence_required,
                            "strong": dimension.strong_indicators,
                            "weak": dimension.weak_indicators,
                        }
                    ),
                },
            )
        author_user_id = connection.execute(
            text(
                """
                INSERT INTO users (
                    identity_subject, email, display_name, email_verified
                ) VALUES (:subject, :email, :display_name, true)
                ON CONFLICT (identity_subject) DO UPDATE SET display_name=EXCLUDED.display_name
                RETURNING id
                """
            ),
            {
                "subject": f"content-author:{question.provenance.author_id}",
                "email": f"{question.provenance.author_id}@content.rigor.test",
                "display_name": question.provenance.author_id,
            },
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO provenance_records (
                    question_version_id, author_id, originality_statement,
                    authoring_method, source_notes
                ) VALUES (
                    :version_id, :author_id, :originality, :method,
                    CAST(:source_notes AS jsonb)
                )
                """
            ),
            {
                "version_id": version_id,
                "author_id": author_user_id,
                "originality": question.provenance.originality_statement,
                "method": question.provenance.authoring_method,
                "source_notes": json.dumps(question.provenance.source_notes),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO validation_runs (
                    question_version_id, validator_version, status, findings,
                    started_at, completed_at
                ) VALUES (
                    :version_id, 'm1-sync-v1', 'passed', '[]'::jsonb,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"version_id": version_id},
        )
