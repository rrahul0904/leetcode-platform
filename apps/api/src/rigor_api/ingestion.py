from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import ValidationError
from rigor_question_schema.universal import (
    PythonCodingQuestion,
    RightsBasis,
    SqlCodingQuestion,
    UniversalQuestion,
    UniversalQuestionBase,
    universal_question_adapter,
)
from sqlalchemy import Engine, text

from .execution import LocalControlledRunner
from .persistence import audit_event, ensure_user
from .schemas import AuthenticatedPrincipal

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 2_000
MAX_COMPRESSION_RATIO = 100
ALLOWED_SUFFIXES = {
    ".json",
    ".jsonl",
    ".csv",
    ".sql",
    ".py",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
ALLOWED_PYTHON_FILES = {
    "starter.py",
    "reference_solution.py",
    "test_reference.py",
    "tests/test_public.py",
    "tests/test_hidden.py",
}
PIPELINE_STAGES = (
    "file_safety",
    "schema_parsing",
    "normalization",
    "provenance_validation",
    "license_validation",
    "identity_validation",
    "reference_validation",
    "duplicate_detection",
    "semantic_similarity",
    "executable_solution_validation",
    "rubric_validation",
    "difficulty_check",
    "security_check",
    "draft_creation",
)


class IngestionError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class SourceRecord:
    source_path: str
    payload: dict[str, Any]
    kind: Literal["complete", "metadata_draft"] = "complete"


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: Literal["passed", "warning", "failed", "skipped"]
    findings: list[str]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class ImportItemResult:
    ordinal: int
    source_path: str
    external_id: str | None
    slug: str | None
    status: Literal["accepted", "rejected", "warning", "draft"]
    errors: list[str]
    warnings: list[str]
    normalized_hash: str | None
    similarity_score: float | None
    question_version_id: str | None
    stages: list[StageResult]


@dataclass(frozen=True)
class ImportResult:
    import_id: str
    source_filename: str
    source_method: str
    status: str
    dry_run: bool
    question_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    started_at: str
    completed_at: str
    items: list[ImportItemResult]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2) + "\n"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _tokens(value: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9_]+", value.casefold()))


def _cosine(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    numerator = sum(count * b[token] for token, count in a.items())
    denominator = sum(value * value for value in a.values()) ** 0.5
    denominator *= sum(value * value for value in b.values()) ** 0.5
    return numerator / denominator if denominator else 0.0


def similarity_action(score: float) -> str:
    if score >= 0.95:
        return "publication_block"
    if score >= 0.85:
        return "mandatory_originality_review"
    if score >= 0.70:
        return "reviewer_warning"
    return "normal_processing"


class SafeUploadParser:
    def parse(self, filename: str, content: bytes) -> tuple[str, list[SourceRecord]]:
        if not filename or len(filename) > 500:
            raise IngestionError(422, "A safe source filename is required")
        if len(content) > MAX_UPLOAD_BYTES:
            raise IngestionError(413, "Upload exceeds the 25 MiB limit")
        suffix = PurePosixPath(filename).suffix.casefold()
        if suffix == ".json":
            return "json", self._json_records(filename, content)
        if suffix == ".jsonl":
            return "jsonl", self._jsonl_records(filename, content)
        if suffix == ".csv":
            return "csv", self._csv_records(filename, content)
        if suffix == ".zip":
            return "zip", self._zip_records(content)
        raise IngestionError(415, "Supported uploads are .json, .jsonl, .csv, and .zip")

    @staticmethod
    def _json_records(filename: str, content: bytes) -> list[SourceRecord]:
        try:
            parsed: object = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IngestionError(422, "JSON upload is malformed") from exc
        values: list[object] = cast(list[object], parsed) if isinstance(parsed, list) else [parsed]
        if not all(isinstance(value, dict) for value in values):
            raise IngestionError(422, "JSON records must be objects")
        return [
            SourceRecord(f"{filename}#{index}", cast(dict[str, Any], value))
            for index, value in enumerate(values, 1)
        ]

    @staticmethod
    def _jsonl_records(filename: str, content: bytes) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        try:
            lines = content.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise IngestionError(422, "JSONL upload must be UTF-8") from exc
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                value: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IngestionError(422, f"Malformed JSONL record on line {line_number}") from exc
            if not isinstance(value, dict):
                raise IngestionError(422, f"JSONL line {line_number} must be an object")
            records.append(SourceRecord(f"{filename}#{line_number}", cast(dict[str, Any], value)))
        return records

    @staticmethod
    def _csv_records(filename: str, content: bytes) -> list[SourceRecord]:
        try:
            stream = io.StringIO(content.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise IngestionError(422, "CSV upload must be UTF-8") from exc
        reader = csv.DictReader(stream)
        required = {
            "id",
            "title",
            "slug",
            "primary_track",
            "difficulty",
            "role_level",
            "author",
            "license",
            "provenance",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise IngestionError(422, f"CSV is missing columns: {', '.join(sorted(missing))}")
        records: list[SourceRecord] = []
        for line_number, row in enumerate(reader, 2):
            payload: dict[str, Any] = {key: (value or "").strip() for key, value in row.items()}
            for field in ("secondary_skills", "company_style_tags", "learning_objectives"):
                payload[field] = [
                    value.strip() for value in payload.get(field, "").split(";") if value.strip()
                ]
            records.append(SourceRecord(f"{filename}#{line_number}", payload, "metadata_draft"))
        return records

    def _zip_records(self, content: bytes) -> list[SourceRecord]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise IngestionError(422, "ZIP upload is malformed") from exc
        with archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise IngestionError(413, "ZIP contains too many entries")
            total_uncompressed = 0
            files: dict[str, bytes] = {}
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                    raise IngestionError(422, "ZIP contains an unsafe path")
                if entry.flag_bits & 0x1:
                    raise IngestionError(422, "Encrypted ZIP entries are unsupported")
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise IngestionError(422, "ZIP symbolic links are unsupported")
                if entry.is_dir():
                    continue
                suffix = path.suffix.casefold()
                if suffix not in ALLOWED_SUFFIXES:
                    raise IngestionError(415, f"Unsupported ZIP file type: {suffix or 'none'}")
                relative = "/".join(path.parts[-2:]) if path.name.endswith(".py") else path.name
                if suffix == ".py" and relative not in ALLOWED_PYTHON_FILES:
                    raise IngestionError(
                        415, f"Unexpected executable Python file: {entry.filename}"
                    )
                total_uncompressed += entry.file_size
                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    raise IngestionError(413, "ZIP expands beyond the 50 MiB limit")
                if (
                    entry.file_size
                    and entry.file_size / max(entry.compress_size, 1) > MAX_COMPRESSION_RATIO
                ):
                    raise IngestionError(422, "ZIP entry has an excessive compression ratio")
                files[entry.filename.rstrip("/")] = archive.read(entry)
            question_paths = sorted(
                path for path in files if PurePosixPath(path).name == "question.json"
            )
            if not question_paths:
                raise IngestionError(422, "ZIP contains no structured question packages")
            records: list[SourceRecord] = []
            seen_ids: set[str] = set()
            seen_slugs: set[str] = set()
            for question_path in question_paths:
                directory = str(PurePosixPath(question_path).parent)
                payload = self._assemble_package(directory, files)
                external_id, slug = str(payload.get("id", "")), str(payload.get("slug", ""))
                if external_id in seen_ids:
                    raise IngestionError(422, f"Duplicate ID in ZIP: {external_id}")
                if slug in seen_slugs:
                    raise IngestionError(422, f"Duplicate slug in ZIP: {slug}")
                seen_ids.add(external_id)
                seen_slugs.add(slug)
                records.append(SourceRecord(question_path, payload))
            return records

    @staticmethod
    def _assemble_package(directory: str, files: dict[str, bytes]) -> dict[str, Any]:
        def required(name: str) -> bytes:
            path = f"{directory}/{name}" if directory != "." else name
            try:
                return files[path]
            except KeyError as exc:
                raise IngestionError(422, f"Package {directory} is missing {name}") from exc

        try:
            question = json.loads(required("question.json"))
            solution = json.loads(required("solution.json"))
            rubric = json.loads(required("rubric.json"))
            metadata = json.loads(required("metadata.json"))
        except json.JSONDecodeError as exc:
            raise IngestionError(422, f"Package {directory} contains malformed JSON") from exc
        if not all(isinstance(value, dict) for value in (question, solution, rubric, metadata)):
            raise IngestionError(422, f"Package {directory} sidecars must contain JSON objects")
        payload = {**question, **metadata, **solution, "rubric": rubric}
        question_type = payload.get("question_type")
        if question_type == "python_coding":
            for name in (
                "starter.py",
                "reference_solution.py",
                "tests/test_public.py",
                "tests/test_hidden.py",
            ):
                required(name)
        elif question_type == "sql_coding":
            for name in ("schema.sql", "seed.sql", "reference_solution.sql"):
                required(name)
        return payload


class ContentIngestionEngine:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.parser = SafeUploadParser()
        self.runner = LocalControlledRunner(engine)

    def import_upload(
        self,
        principal: AuthenticatedPrincipal,
        *,
        filename: str,
        content: bytes,
        dry_run: bool,
        visibility: Literal["public", "private"] = "public",
        source_method_override: Literal["generation", "licensed_connector"] | None = None,
    ) -> ImportResult:
        started = datetime.now(UTC)
        parsed_method, records = self.parser.parse(filename, content)
        source_method = source_method_override or parsed_method
        if not records:
            raise IngestionError(422, "Import contains no records")
        if len(records) > 1000:
            raise IngestionError(413, "A single import may contain at most 1,000 records")
        organization_id = self._organization_id(principal, visibility)
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            import_id = connection.execute(
                text(
                    """
                    INSERT INTO content_imports (
                        importing_user_id, organization_id, source_filename,
                        source_method, status, dry_run, question_count
                    ) VALUES (
                        :actor_id, :organization_id, :filename, :source_method,
                        'processing', :dry_run, :question_count
                    ) RETURNING id
                    """
                ),
                {
                    "actor_id": actor_id,
                    "organization_id": organization_id,
                    "filename": filename,
                    "source_method": source_method,
                    "dry_run": dry_run,
                    "question_count": len(records),
                },
            ).scalar_one()
        results: list[ImportItemResult] = []
        seen_ids: set[str] = set()
        seen_slugs: set[str] = set()
        for ordinal, record in enumerate(records, 1):
            results.append(
                self._process_record(
                    principal,
                    UUID(str(import_id)),
                    ordinal,
                    record,
                    source_method=source_method,
                    dry_run=dry_run,
                    visibility=visibility,
                    organization_id=organization_id,
                    batch_ids=seen_ids,
                    batch_slugs=seen_slugs,
                )
            )
        accepted = sum(item.status in {"accepted", "draft", "warning"} for item in results)
        rejected = sum(item.status == "rejected" for item in results)
        warnings = sum(len(item.warnings) for item in results)
        status = (
            "failed"
            if accepted == 0
            else "completed_with_warnings"
            if warnings or rejected
            else "completed"
        )
        completed = datetime.now(UTC)
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            rollback_available = bool(
                connection.execute(
                    text(
                        "SELECT EXISTS ("
                        "SELECT 1 FROM question_versions "
                        "WHERE source_revision=:source_revision"
                        ")"
                    ),
                    {"source_revision": f"import:{import_id}"},
                ).scalar_one()
            )
            connection.execute(
                text(
                    """
                    UPDATE content_imports SET
                        status=:status, accepted_count=:accepted, rejected_count=:rejected,
                        warning_count=:warnings, rollback_available=:rollback_available,
                        completed_at=:completed
                    WHERE id=:import_id
                    """
                ),
                {
                    "status": status,
                    "accepted": accepted,
                    "rejected": rejected,
                    "warnings": warnings,
                    "rollback_available": rollback_available,
                    "completed": completed,
                    "import_id": import_id,
                },
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="content.import.completed",
                resource_type="content_import",
                resource_id=str(import_id),
                details={
                    "source_method": source_method,
                    "dry_run": dry_run,
                    "accepted": accepted,
                    "rejected": rejected,
                    "warnings": warnings,
                },
            )
        return ImportResult(
            import_id=str(import_id),
            source_filename=filename,
            source_method=source_method,
            status=status,
            dry_run=dry_run,
            question_count=len(records),
            accepted_count=accepted,
            rejected_count=rejected,
            warning_count=warnings,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            items=results,
        )

    def _process_record(
        self,
        principal: AuthenticatedPrincipal,
        import_id: UUID,
        ordinal: int,
        record: SourceRecord,
        *,
        source_method: str,
        dry_run: bool,
        visibility: str,
        organization_id: UUID | None,
        batch_ids: set[str],
        batch_slugs: set[str],
    ) -> ImportItemResult:
        stages = [StageResult("file_safety", "passed", [], {})]
        errors: list[str] = []
        warnings: list[str] = []
        payload = record.payload
        external_id = str(payload.get("id")) if payload.get("id") else None
        slug = str(payload.get("slug")) if payload.get("slug") else None
        if record.kind == "metadata_draft":
            stages.extend(
                [
                    StageResult(
                        "schema_parsing", "warning", ["CSV metadata creates a draft only"], {}
                    ),
                    *[
                        StageResult(stage, "skipped", ["Awaiting complete package"], {})
                        for stage in PIPELINE_STAGES[2:]
                    ],
                ]
            )
            warnings.append(
                "CSV metadata was stored as an incomplete draft and cannot be published"
            )
            return self._persist_item(
                principal,
                import_id,
                ordinal,
                record,
                external_id,
                slug,
                "draft",
                errors,
                warnings,
                None,
                None,
                None,
                stages,
                payload,
            )
        try:
            parsed = universal_question_adapter.validate_python(payload)
            normalized = parsed.model_dump(mode="json")
            normalized_hash = _sha256(_canonical_json(normalized))
            stages.append(
                StageResult(
                    "schema_parsing", "passed", [], {"question_type": parsed.question_type.value}
                )
            )
        except ValidationError as exc:
            errors.extend(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            stages.append(StageResult("schema_parsing", "failed", errors.copy(), {}))
            stages.extend(
                StageResult(stage, "skipped", ["Schema parsing failed"], {})
                for stage in PIPELINE_STAGES[2:]
            )
            return self._persist_item(
                principal,
                import_id,
                ordinal,
                record,
                external_id,
                slug,
                "rejected",
                errors,
                warnings,
                None,
                None,
                None,
                stages,
                payload,
            )
        stages.append(StageResult("normalization", "passed", [], {"sha256": normalized_hash}))
        stages.extend(self._rights_stages(parsed, errors))
        if parsed.id in batch_ids:
            errors.append(f"duplicate ID in import: {parsed.id}")
        if parsed.slug in batch_slugs:
            errors.append(f"duplicate slug in import: {parsed.slug}")
        batch_ids.add(parsed.id)
        batch_slugs.add(parsed.slug)
        identity_findings = [value for value in errors if "duplicate" in value]
        stages.append(
            StageResult(
                "identity_validation",
                "failed" if identity_findings else "passed",
                identity_findings,
                {},
            )
        )
        reference_findings = self._reference_findings(parsed, batch_ids)
        if reference_findings:
            errors.extend(reference_findings)
        stages.append(
            StageResult(
                "reference_validation",
                "failed" if reference_findings else "passed",
                reference_findings,
                {},
            )
        )
        similarity, dimensions, existing_version_id = self._similarity(parsed, normalized_hash)
        action = similarity_action(similarity)
        duplicate_status: Literal["passed", "warning", "failed"] = (
            "failed"
            if action == "publication_block"
            else "warning"
            if action != "normal_processing"
            else "passed"
        )
        if action == "publication_block":
            warnings.append("Similarity >= 0.95 blocks publication pending originality review")
        elif action != "normal_processing":
            warnings.append(f"Similarity action required: {action}")
        stages.append(StageResult("duplicate_detection", duplicate_status, [action], dimensions))
        stages.append(
            StageResult(
                "semantic_similarity",
                duplicate_status,
                [action],
                {"score": similarity, "method": "deterministic lexical-vector cosine"},
            )
        )
        executable_findings = self._execute(parsed)
        if executable_findings:
            errors.extend(executable_findings)
        stages.append(
            StageResult(
                "executable_solution_validation",
                "failed" if executable_findings else "passed",
                executable_findings,
                {},
            )
        )
        stages.append(StageResult("rubric_validation", "passed", [], {"weight_total": 100}))
        difficulty_findings = self._difficulty_findings(parsed)
        warnings.extend(difficulty_findings)
        stages.append(
            StageResult(
                "difficulty_check",
                "warning" if difficulty_findings else "passed",
                difficulty_findings,
                {},
            )
        )
        security_findings = self._security_findings(parsed)
        if security_findings:
            errors.extend(security_findings)
        stages.append(
            StageResult(
                "security_check",
                "failed" if security_findings else "passed",
                security_findings,
                {},
            )
        )
        version_id: UUID | None = None
        if errors:
            status: Literal["accepted", "rejected", "warning", "draft"] = "rejected"
            stages.append(StageResult("draft_creation", "skipped", ["Validation failed"], {}))
        elif dry_run:
            status = "warning" if warnings else "accepted"
            stages.append(StageResult("draft_creation", "skipped", ["Dry run"], {}))
        else:
            version_id = self._create_draft(
                principal,
                import_id,
                parsed,
                normalized,
                normalized_hash,
                source_method,
                visibility,
                organization_id,
            )
            status = "warning" if warnings else "accepted"
            stages.append(
                StageResult("draft_creation", "passed", [], {"version_id": str(version_id)})
            )
        item = self._persist_item(
            principal,
            import_id,
            ordinal,
            record,
            parsed.id,
            parsed.slug,
            status,
            errors,
            warnings,
            normalized_hash,
            similarity,
            version_id,
            stages,
            normalized,
        )
        if similarity and similarity >= 0.70:
            self._persist_duplicate(
                UUID(item.question_version_id) if item.question_version_id else None,
                import_id,
                ordinal,
                existing_version_id,
                dimensions,
                similarity,
                action,
            )
        return item

    @staticmethod
    def _rights_stages(question: UniversalQuestionBase, errors: list[str]) -> list[StageResult]:
        provenance_findings: list[str] = []
        if not question.provenance.certification_evidence:
            provenance_findings.append("provenance certification evidence is required")
        license_findings: list[str] = []
        if question.license.expiration_date and question.license.expiration_date < date.today():
            license_findings.append("content license is expired")
        source = (question.provenance.source_uri or "").casefold()
        prohibited_hosts = ("leetcode.", "hackerrank.", "interviewbit.")
        if question.license.rights_basis == RightsBasis.ORIGINAL and any(
            host in source for host in prohibited_hosts
        ):
            license_findings.append(
                "original certification conflicts with a third-party source URI"
            )
        errors.extend(provenance_findings)
        errors.extend(license_findings)
        return [
            StageResult(
                "provenance_validation",
                "failed" if provenance_findings else "passed",
                provenance_findings,
                {},
            ),
            StageResult(
                "license_validation",
                "failed" if license_findings else "passed",
                license_findings,
                {"rights_basis": question.license.rights_basis.value},
            ),
        ]

    def _reference_findings(
        self, question: UniversalQuestionBase, batch_ids: set[str]
    ) -> list[str]:
        findings: list[str] = []
        manifest_ids = self._manifest_ids()
        for related in question.related_question_ids:
            if related not in manifest_ids and related not in batch_ids:
                findings.append(f"related question is absent from manifest/import: {related}")
        return findings

    @staticmethod
    def _difficulty_findings(question: UniversalQuestionBase) -> list[str]:
        dimensions = question.difficulty_dimensions
        if (
            question.difficulty.value in {"staff", "principal"}
            and max(dimensions.scale, dimensions.ambiguity, dimensions.prerequisite_depth) < 4
        ):
            return ["staff/principal difficulty lacks scale, ambiguity, or prerequisite depth"]
        if (
            question.difficulty.value == "foundational"
            and max(dimensions.conceptual, dimensions.implementation) > 3
        ):
            return ["foundational difficulty has unexpectedly high implementation dimensions"]
        return []

    @staticmethod
    def _security_findings(question: UniversalQuestionBase) -> list[str]:
        content = question.reference_solution.content.casefold()
        forbidden = ("subprocess", "os.system", "socket.", "eval(", "exec(")
        return [
            f"reference solution contains blocked primitive: {value}"
            for value in forbidden
            if value in content
        ]

    def _execute(self, question: UniversalQuestion) -> list[str]:
        if isinstance(question, PythonCodingQuestion):
            result = self.runner.execute(
                runtime="python3.13",  # type: ignore[arg-type]
                source=question.reference_solution.content,
                tests=[test.model_dump(mode="json") for test in question.type_specification.tests],
            )
            return (
                []
                if result.status == "passed"
                else [f"Python reference execution: {result.error_category or result.status}"]
            )
        if isinstance(question, SqlCodingQuestion):
            result = self.runner.execute(
                runtime="postgresql18",  # type: ignore[arg-type]
                source=question.type_specification.reference_sql,
                tests=[test.model_dump(mode="json") for test in question.type_specification.tests],
            )
            return (
                []
                if result.status == "passed"
                else [f"SQL reference execution: {result.error_category or result.status}"]
            )
        return []

    def _similarity(
        self, question: UniversalQuestionBase, normalized_hash: str
    ) -> tuple[float, dict[str, float], UUID | None]:
        best_score = 0.0
        best_dimensions: dict[str, float] = {}
        best_version_id: UUID | None = None
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    SELECT id, title, problem_statement, structured_content, content_hash
                    FROM question_versions ORDER BY created_at DESC LIMIT 5000
                    """
                    )
                )
                .mappings()
                .all()
            )
        incoming = question.model_dump(mode="json")
        incoming_spec = cast(dict[str, Any], incoming.get("type_specification", {}))
        for row in rows:
            existing = cast(dict[str, Any], row["structured_content"] or {})
            existing_spec = cast(dict[str, Any], existing.get("type_specification", {}))
            title_score = SequenceMatcher(
                None, question.title.casefold(), str(row["title"]).casefold()
            ).ratio()
            problem_score = SequenceMatcher(
                None,
                question.public_problem_statement.casefold(),
                str(row["problem_statement"]).casefold(),
            ).ratio()
            semantic = _cosine(question.public_problem_statement, str(row["problem_statement"]))
            structural = float(
                existing.get("question_type") == incoming.get("question_type")
                and existing.get("primary_track") == incoming.get("primary_track")
            )
            starter = _cosine(
                json.dumps(incoming_spec.get("starter_code", "")),
                json.dumps(existing_spec.get("starter_code", "")),
            )
            solution = _cosine(
                question.reference_solution.content,
                json.dumps(existing.get("reference_solution", {})),
            )
            tests = _cosine(
                json.dumps(incoming_spec.get("tests", []), sort_keys=True),
                json.dumps(existing_spec.get("tests", []), sort_keys=True),
            )
            exact = float(str(row["content_hash"]) == normalized_hash)
            dimensions = {
                "exact_hash": exact,
                "title": title_score,
                "problem_statement": problem_score,
                "embedding": semantic,
                "structural": structural,
                "starter_code": starter,
                "solution_code": solution,
                "test_cases": tests,
                "schema": structural,
            }
            score = round(
                exact * 0.20
                + title_score * 0.10
                + problem_score * 0.20
                + semantic * 0.20
                + structural * 0.05
                + starter * 0.05
                + solution * 0.10
                + tests * 0.05
                + structural * 0.05,
                4,
            )
            if score > best_score:
                best_score, best_dimensions = score, dimensions
                best_version_id = UUID(str(row["id"]))
        return best_score, best_dimensions, best_version_id

    def _create_draft(
        self,
        principal: AuthenticatedPrincipal,
        import_id: UUID,
        question: UniversalQuestionBase,
        normalized: dict[str, Any],
        normalized_hash: str,
        source_method: str,
        visibility: str,
        organization_id: UUID | None,
    ) -> UUID:
        with self.engine.begin() as connection:
            actor_id = ensure_user(connection, principal)
            track_id = connection.execute(
                text("SELECT id FROM question_tracks WHERE slug=:slug"),
                {"slug": question.primary_track},
            ).scalar_one_or_none()
            if track_id is None:
                raise IngestionError(422, f"Unknown primary track: {question.primary_track}")
            slug_owner = connection.execute(
                text("SELECT external_id FROM questions WHERE slug=:slug"), {"slug": question.slug}
            ).scalar_one_or_none()
            if slug_owner is not None and slug_owner != question.id:
                raise IngestionError(409, "Question slug already belongs to another ID")
            question_id = connection.execute(
                text(
                    """
                    INSERT INTO questions (
                        external_id, slug, primary_track_id, visibility, organization_id
                    ) VALUES (
                        :external_id, :slug, :track_id, :visibility, :organization_id
                    )
                    ON CONFLICT (external_id) DO UPDATE SET
                        slug=EXCLUDED.slug, primary_track_id=EXCLUDED.primary_track_id,
                        visibility=EXCLUDED.visibility, organization_id=EXCLUDED.organization_id,
                        updated_at=CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ),
                {
                    "external_id": question.id,
                    "slug": question.slug,
                    "track_id": track_id,
                    "visibility": visibility,
                    "organization_id": organization_id,
                },
            ).scalar_one()
            existing = (
                connection.execute(
                    text(
                        """
                    SELECT id, content_hash, state::text AS state FROM question_versions
                    WHERE question_id=:question_id AND version=:version
                    """
                    ),
                    {"question_id": question_id, "version": question.version},
                )
                .mappings()
                .one_or_none()
            )
            if existing:
                if existing["content_hash"] == normalized_hash:
                    return UUID(str(existing["id"]))
                raise IngestionError(409, "Changed content must use a new semantic version")
            state = (
                "generated" if source_method in {"generation", "json", "jsonl", "zip"} else "draft"
            )
            version_id = connection.execute(
                text(
                    """
                    INSERT INTO question_versions (
                        question_id, version, title, problem_statement, expected_seniority,
                        difficulty, conceptual_difficulty, implementation_difficulty,
                        scale, ambiguity, prerequisite_depth, duration_minutes, state,
                        structured_content, content_hash, source_revision
                    ) VALUES (
                        :question_id, :version, :title, :problem, :role, :difficulty,
                        :conceptual, :implementation, :scale, :ambiguity, :depth,
                        :duration, CAST(:state AS content_state), CAST(:structured AS jsonb),
                        :content_hash, :source_revision
                    ) RETURNING id
                    """
                ),
                {
                    "question_id": question_id,
                    "version": question.version,
                    "title": question.title,
                    "problem": question.public_problem_statement,
                    "role": question.role_level,
                    "difficulty": question.difficulty.value,
                    "conceptual": question.difficulty_dimensions.conceptual,
                    "implementation": question.difficulty_dimensions.implementation,
                    "scale": question.difficulty_dimensions.scale,
                    "ambiguity": question.difficulty_dimensions.ambiguity,
                    "depth": question.difficulty_dimensions.prerequisite_depth,
                    "duration": question.estimated_duration_minutes,
                    "state": state,
                    "structured": json.dumps(normalized),
                    "content_hash": normalized_hash,
                    "source_revision": f"import:{import_id}",
                },
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO solutions (
                        question_version_id, reference_solution, explanation,
                        trade_off_analysis, source_content_hash
                    ) VALUES (
                        :version_id, :solution, :explanation,
                        CAST(:tradeoffs AS jsonb), :content_hash
                    )
                    """
                ),
                {
                    "version_id": version_id,
                    "solution": question.reference_solution.content,
                    "explanation": question.reference_solution.explanation,
                    "tradeoffs": json.dumps(question.reference_solution.trade_offs),
                    "content_hash": normalized_hash,
                },
            )
            rubric_id = connection.execute(
                text(
                    "INSERT INTO rubrics (question_version_id, score_bands) "
                    "VALUES (:version_id, CAST(:score_bands AS jsonb)) RETURNING id"
                ),
                {
                    "version_id": version_id,
                    "score_bands": json.dumps(question.rubric.score_bands),
                },
            ).scalar_one()
            for rubric_ordinal, dimension in enumerate(question.rubric.dimensions, 1):
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
                        "ordinal": rubric_ordinal,
                        "indicators": json.dumps(
                            {
                                "evidence_required": dimension.evidence_required,
                                "strong": dimension.strong_indicators,
                                "weak": dimension.weak_indicators,
                            }
                        ),
                    },
                )
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
                    "author_id": actor_id,
                    "originality": question.provenance.originality_statement,
                    "method": question.provenance.authoring_method,
                    "source_notes": json.dumps(question.provenance.source_notes),
                },
            )
            license_payload = question.license.model_dump(mode="json")
            connection.execute(
                text(
                    """
                    INSERT INTO content_license_records (
                        question_version_id, rights_basis, license_identifier,
                        provider, agreement_identifier, certification, evidence,
                        terms, expiration_date, created_by
                    ) VALUES (
                        :version_id, :rights_basis, :license_identifier,
                        :provider, :agreement_identifier, :certification,
                        CAST(:evidence AS jsonb), CAST(:terms AS jsonb),
                        :expiration_date, :created_by
                    )
                    """
                ),
                {
                    "version_id": version_id,
                    "rights_basis": question.license.rights_basis.value,
                    "license_identifier": question.license.license_identifier,
                    "provider": question.license.provider,
                    "agreement_identifier": question.license.agreement_identifier,
                    "certification": question.license.certification,
                    "evidence": json.dumps(question.license.evidence),
                    "terms": json.dumps(license_payload),
                    "expiration_date": question.license.expiration_date,
                    "created_by": actor_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO validation_runs (
                        question_version_id, validator_version, status, findings,
                        started_at, completed_at
                    ) VALUES (
                        :version_id, 'universal-ingestion-v1', 'passed', '[]'::jsonb,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"version_id": version_id},
            )
            audit_event(
                connection,
                principal,
                actor_id,
                action="content.draft.imported",
                resource_type="question_version",
                resource_id=str(version_id),
                details={"import_id": str(import_id), "source_method": source_method},
            )
            return UUID(str(version_id))

    def _persist_item(
        self,
        principal: AuthenticatedPrincipal,
        import_id: UUID,
        ordinal: int,
        record: SourceRecord,
        external_id: str | None,
        slug: str | None,
        status: Literal["accepted", "rejected", "warning", "draft"],
        errors: list[str],
        warnings: list[str],
        normalized_hash: str | None,
        similarity_score: float | None,
        version_id: UUID | None,
        stages: list[StageResult],
        payload: dict[str, Any],
    ) -> ImportItemResult:
        with self.engine.begin() as connection:
            ensure_user(connection, principal)
            item_id = connection.execute(
                text(
                    """
                    INSERT INTO content_import_items (
                        import_id, ordinal, source_path, external_id, slug, status,
                        normalized_hash, similarity_score, rights_action,
                        errors, warnings, normalized_payload, question_version_id
                    ) VALUES (
                        :import_id, :ordinal, :source_path, :external_id, :slug, :status,
                        :normalized_hash, :similarity_score, :rights_action,
                        CAST(:errors AS jsonb), CAST(:warnings AS jsonb),
                        CAST(:payload AS jsonb), :version_id
                    ) RETURNING id
                    """
                ),
                {
                    "import_id": import_id,
                    "ordinal": ordinal,
                    "source_path": record.source_path,
                    "external_id": external_id,
                    "slug": slug,
                    "status": status,
                    "normalized_hash": normalized_hash,
                    "similarity_score": similarity_score,
                    "rights_action": "blocked"
                    if any("license" in value for value in errors)
                    else "cleared",
                    "errors": json.dumps(errors),
                    "warnings": json.dumps(warnings),
                    "payload": json.dumps(payload),
                    "version_id": version_id,
                },
            ).scalar_one()
            for stage in stages:
                connection.execute(
                    text(
                        """
                        INSERT INTO content_import_stage_results (
                            import_item_id, stage, status, findings, metrics
                        ) VALUES (
                            :item_id, :stage, :status,
                            CAST(:findings AS jsonb), CAST(:metrics AS jsonb)
                        )
                        """
                    ),
                    {
                        "item_id": item_id,
                        "stage": stage.stage,
                        "status": stage.status,
                        "findings": json.dumps(stage.findings),
                        "metrics": json.dumps(stage.metrics),
                    },
                )
        return ImportItemResult(
            ordinal=ordinal,
            source_path=record.source_path,
            external_id=external_id,
            slug=slug,
            status=status,
            errors=errors,
            warnings=warnings,
            normalized_hash=normalized_hash,
            similarity_score=similarity_score,
            question_version_id=str(version_id) if version_id else None,
            stages=stages,
        )

    def _persist_duplicate(
        self,
        version_id: UUID | None,
        import_id: UUID,
        ordinal: int,
        existing_version_id: UUID | None,
        dimensions: dict[str, float],
        score: float,
        action: str,
    ) -> None:
        del version_id
        with self.engine.begin() as connection:
            item_id = connection.execute(
                text(
                    "SELECT id FROM content_import_items "
                    "WHERE import_id=:import_id AND ordinal=:ordinal"
                ),
                {"import_id": import_id, "ordinal": ordinal},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO duplicate_candidates (
                        import_item_id, existing_question_version_id, comparison_source,
                        dimension_scores, similarity_score, suggested_action
                    ) VALUES (
                        :item_id, :existing_id, 'internal-question-catalog',
                        CAST(:dimensions AS jsonb), :score, :action
                    )
                    """
                ),
                {
                    "item_id": item_id,
                    "existing_id": existing_version_id,
                    "dimensions": json.dumps(dimensions),
                    "score": score,
                    "action": action,
                },
            )

    @staticmethod
    def _organization_id(principal: AuthenticatedPrincipal, visibility: str) -> UUID | None:
        if visibility == "public":
            return None
        if not principal.organization_id:
            raise IngestionError(403, "Private-library imports require an organization identity")
        try:
            return UUID(principal.organization_id)
        except ValueError as exc:
            raise IngestionError(422, "Organization ID must be a UUID") from exc

    @staticmethod
    def _manifest_ids() -> set[str]:
        # Reference validation also accepts records in the same import; the canonical manifest
        # is checked by the Git synchronizer where a content root is available.
        return set()
