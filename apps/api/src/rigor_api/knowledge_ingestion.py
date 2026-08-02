from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import stat
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import cast

MAX_ARCHIVE_ENTRIES = 25_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_CODE_BYTES = 2 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".csv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
}
CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".sql",
    ".java",
    ".cpp",
    ".c++",
    ".cc",
    ".c",
    ".cs",
    ".go",
    ".kt",
    ".dart",
}
QUARANTINE_SUFFIXES = {
    ".exe",
    ".out",
    ".obj",
    ".dll",
    ".so",
    ".dylib",
    ".class",
    ".jar",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
}
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sql": "sql",
    ".java": "java",
    ".cpp": "cpp",
    ".c++": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".go": "go",
    ".kt": "kotlin",
    ".dart": "dart",
}

PROBLEM_DIRECTORY = re.compile(r"^\s*(?P<id>\d+)\.\s*(?P<title>.+?)\s*$")
LEETCODE_SLUG = re.compile(
    r"(?:https?://)?leetcode\.com/problems/(?P<slug>[a-z0-9-]+)",
    re.IGNORECASE,
)
HEADING = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
HTML_TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
NON_SLUG = re.compile(r"[^a-z0-9]+")
TOPIC_SEPARATOR = re.compile(r"[,|;\n]+")


class SourceDisposition(StrEnum):
    HOSTABLE_LICENSED = "hostable_licensed"
    EXTERNAL_REFERENCE_ONLY = "external_reference_only"
    RIGHTS_REVIEW_REQUIRED = "rights_review_required"
    REJECTED_PROPRIETARY = "rejected_proprietary"


class ArchiveSafetyError(ValueError):
    pass


@dataclass(frozen=True)
class ArchiveInventory:
    archive_name: str
    archive_sha256: str
    compressed_bytes: int
    uncompressed_bytes: int
    file_count: int
    suffix_counts: dict[str, int]
    duplicate_of: str | None = None


@dataclass(frozen=True)
class SourceFileRecord:
    source_name: str
    relative_path: str
    sha256: str
    byte_count: int
    suffix: str
    classification: str
    parse_status: str
    error: str | None = None


@dataclass(frozen=True)
class ProblemObservation:
    canonical_key: str
    external_id: str | None
    title: str
    slug: str
    description: str | None
    difficulty: str | None
    source_url: str | None
    topics: tuple[str, ...]
    source_name: str
    source_path: str
    source_hash: str
    disposition: SourceDisposition


@dataclass(frozen=True)
class SolutionObservation:
    canonical_key: str
    language: str
    source_code: str
    explanation: str | None
    time_complexity: str | None
    space_complexity: str | None
    source_name: str
    source_path: str
    source_hash: str
    disposition: SourceDisposition


@dataclass(frozen=True)
class CompanyObservation:
    canonical_key: str
    external_id: str | None
    title: str
    problem_url: str | None
    company: str
    observation_window: str | None
    difficulty: str | None
    acceptance_rate: float | None
    frequency: float | None
    topics: tuple[str, ...]
    source_name: str
    source_path: str
    source_hash: str


@dataclass(frozen=True)
class SystemDesignObservation:
    slug: str
    title: str
    body: str
    headings: tuple[str, ...]
    image_paths: tuple[str, ...]
    source_name: str
    source_path: str
    source_hash: str
    disposition: SourceDisposition


@dataclass(frozen=True)
class LearningResourceObservation:
    slug: str
    title: str
    category: str
    language: str | None
    body: str
    source_name: str
    source_path: str
    source_hash: str
    disposition: SourceDisposition


@dataclass
class IngestionBundle:
    source_name: str
    disposition: SourceDisposition
    files: list[SourceFileRecord] = field(default_factory=list)
    problems: list[ProblemObservation] = field(default_factory=list)
    solutions: list[SolutionObservation] = field(default_factory=list)
    companies: list[CompanyObservation] = field(default_factory=list)
    system_design: list[SystemDesignObservation] = field(default_factory=list)
    resources: list[LearningResourceObservation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "disposition": self.disposition.value,
            "counts": {
                "files": len(self.files),
                "problems": len(self.problems),
                "solutions": len(self.solutions),
                "company_observations": len(self.companies),
                "system_design_articles": len(self.system_design),
                "learning_resources": len(self.resources),
                "warnings": len(self.warnings),
            },
            "files": [serialize_dataclass(item) for item in self.files],
            "problems": [serialize_dataclass(item) for item in self.problems],
            "solutions": [serialize_dataclass(item) for item in self.solutions],
            "companies": [serialize_dataclass(item) for item in self.companies],
            "system_design": [serialize_dataclass(item) for item in self.system_design],
            "resources": [serialize_dataclass(item) for item in self.resources],
            "warnings": self.warnings,
        }


def serialize_dataclass(value: object) -> dict[str, object]:
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError("Knowledge ingestion records must be dataclass instances")
    payload = cast(dict[str, object], asdict(value))
    disposition = payload.get("disposition")
    if isinstance(disposition, SourceDisposition):
        payload["disposition"] = disposition.value
    return payload


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    normalized = NON_SLUG.sub("-", value.casefold()).strip("-")
    return normalized or "untitled"


def normalize_title(value: str) -> str:
    return SPACE.sub(" ", HTML_TAG.sub(" ", value)).strip(" -#\t\r\n")


def normalize_company(value: str) -> str:
    text = value.replace("_", " ").replace("-", " ")
    aliases = {
        "amazon web services": "Amazon",
        "aws": "Amazon",
        "facebook": "Meta",
        "google llc": "Google",
        "microsoft corporation": "Microsoft",
        "bookingcom": "Booking.com",
        "jpmorgan": "JPMorgan Chase",
        "jp morgan": "JPMorgan Chase",
    }
    compact = SPACE.sub(" ", text).strip().casefold()
    if compact in aliases:
        return aliases[compact]
    return " ".join(part.capitalize() for part in compact.split())


def normalize_topic(value: str) -> str:
    aliases = {
        "two pointer": "two-pointers",
        "two pointers": "two-pointers",
        "sliding window": "sliding-window",
        "dynamic programming": "dynamic-programming",
        "breadth first search": "breadth-first-search",
        "depth first search": "depth-first-search",
        "binary search": "binary-search",
        "linked list": "linked-list",
        "hash table": "hashing",
    }
    normalized = (
        SPACE.sub(
            " ",
            value.replace("_", " ").replace("-", " "),
        )
        .strip()
        .casefold()
    )
    return aliases.get(normalized, slugify(normalized))


def normalize_difficulty(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    aliases = {
        "easy": "easy",
        "medium": "medium",
        "hard": "hard",
        "beginner": "easy",
        "intermediate": "medium",
        "advanced": "hard",
    }
    return aliases.get(normalized)


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    candidate = value.strip().replace("%", "").replace(",", "")
    if not candidate:
        return None
    try:
        return float(candidate)
    except ValueError:
        return None


def canonical_problem_key(
    *,
    external_id: str | None,
    title: str,
    source_url: str | None,
) -> str:
    if external_id and external_id.strip().isdigit():
        return f"leetcode:{int(external_id)}"
    if source_url:
        match = LEETCODE_SLUG.search(source_url)
        if match:
            return f"leetcode-slug:{match.group('slug').casefold()}"
    return f"normalized-title:{slugify(title)}"


def read_text(path: Path, *, maximum: int = MAX_TEXT_BYTES) -> str:
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError(f"{path.name} exceeds the parser byte limit")
    return raw.decode("utf-8-sig", errors="replace")


def markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"preamble": []}
    current = "preamble"
    for line in body.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = normalize_title(heading.group("title")).casefold()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def complexity_from_markdown(body: str) -> tuple[str | None, str | None]:
    time_match = re.search(
        r"time\s+complexity\s*[:|\-]*\s*`?([^\n|`]+)",
        body,
        flags=re.IGNORECASE,
    )
    space_match = re.search(
        r"space\s+complexity\s*[:|\-]*\s*`?([^\n|`]+)",
        body,
        flags=re.IGNORECASE,
    )
    return (
        normalize_title(time_match.group(1)) if time_match else None,
        normalize_title(space_match.group(1)) if space_match else None,
    )


def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    mode = member.external_attr >> 16
    return stat.S_ISLNK(mode)


def inspect_archive(
    path: Path,
    *,
    duplicate_of: str | None = None,
) -> ArchiveInventory:
    if not path.is_file():
        raise ArchiveSafetyError(f"Archive does not exist: {path}")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ArchiveSafetyError(f"Malformed ZIP archive: {path.name}") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ArchiveSafetyError(f"Archive contains too many entries: {path.name}")
        total = 0
        suffixes: Counter[str] = Counter()
        for member in entries:
            relative = PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts or "\\" in member.filename:
                raise ArchiveSafetyError(f"Unsafe archive path: {member.filename}")
            if _zip_member_is_symlink(member):
                raise ArchiveSafetyError(f"Archive contains a symbolic link: {member.filename}")
            total += member.file_size
            if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ArchiveSafetyError(f"Archive expands beyond the allowed limit: {path.name}")
            if (
                member.compress_size
                and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ArchiveSafetyError(f"Suspicious compression ratio: {member.filename}")
            if not member.is_dir():
                suffix = PurePosixPath(member.filename).suffix.casefold()
                suffixes[suffix or "<none>"] += 1
        return ArchiveInventory(
            archive_name=path.name,
            archive_sha256=sha256_file(path),
            compressed_bytes=path.stat().st_size,
            uncompressed_bytes=total,
            file_count=sum(suffixes.values()),
            suffix_counts=dict(suffixes.most_common()),
            duplicate_of=duplicate_of,
        )


def inventory_archives(directory: Path) -> list[ArchiveInventory]:
    archives = sorted(
        directory.glob("*.zip"),
        key=lambda item: item.name.casefold(),
    )
    seen: dict[str, str] = {}
    result: list[ArchiveInventory] = []
    for archive in archives:
        digest = sha256_file(archive)
        duplicate = seen.get(digest)
        result.append(inspect_archive(archive, duplicate_of=duplicate))
        seen.setdefault(digest, archive.name)
    return result


def extract_archive(path: Path, destination: Path) -> ArchiveInventory:
    inventory = inspect_archive(path)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = PurePosixPath(member.filename)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return inventory


def classify_file(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in QUARANTINE_SUFFIXES:
        return "quarantined"
    if suffix in CODE_SUFFIXES:
        return "source_code"
    if suffix in TEXT_SUFFIXES:
        return "structured_text"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        return "image"
    return "unsupported"


def source_file_record(
    path: Path,
    root: Path,
    source_name: str,
) -> SourceFileRecord:
    classification = classify_file(path)
    try:
        digest = sha256_file(path)
        byte_count = path.stat().st_size
        status = "skipped" if classification in {"quarantined", "unsupported"} else "available"
        return SourceFileRecord(
            source_name=source_name,
            relative_path=path.relative_to(root).as_posix(),
            sha256=digest,
            byte_count=byte_count,
            suffix=path.suffix.casefold(),
            classification=classification,
            parse_status=status,
        )
    except OSError as exc:
        return SourceFileRecord(
            source_name=source_name,
            relative_path=path.relative_to(root).as_posix(),
            sha256="",
            byte_count=0,
            suffix=path.suffix.casefold(),
            classification=classification,
            parse_status="failed",
            error=str(exc),
        )


def _problem_identity_from_directory(
    path: Path,
) -> tuple[str | None, str] | None:
    match = PROBLEM_DIRECTORY.match(path.name)
    if not match:
        return None
    return match.group("id"), normalize_title(match.group("title"))


def _problem_markdown(directory: Path) -> Path | None:
    candidates = [
        directory / "README.md",
        directory / "Explanation" / "explanation.md",
        directory / "explanation.md",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _description_from_markdown(body: str) -> str | None:
    sections = markdown_sections(body)
    preferred = (
        "problem description",
        "problem statement",
        "problem summary",
        "description",
    )
    for name in preferred:
        value = sections.get(name)
        if value:
            return value
    preamble = sections.get("preamble", "")
    candidates = [value for name, value in sections.items() if name != "preamble" and value]
    if preamble:
        candidates.append(preamble)
    return max(candidates, key=len) if candidates else None


def _topics_from_markdown(body: str) -> tuple[str, ...]:
    sections = markdown_sections(body)
    candidates: list[str] = []
    for name in ("topics", "topic", "tags", "data structures used"):
        value = sections.get(name, "")
        if not value:
            continue
        for raw_topic in TOPIC_SEPARATOR.split(value):
            topic = re.sub(r"^[-*]\s*", "", raw_topic).strip()
            if topic and len(topic.split()) <= 5:
                candidates.append(topic)
    normalized = sorted({normalize_topic(value) for value in candidates})
    return tuple(normalized[:30])


def parse_problem_directories(
    root: Path,
    *,
    source_name: str,
    disposition: SourceDisposition,
) -> tuple[list[ProblemObservation], list[SolutionObservation], list[str]]:
    problems: list[ProblemObservation] = []
    solutions: list[SolutionObservation] = []
    warnings: list[str] = []
    seen_directories: set[Path] = set()

    for directory in sorted(path for path in root.rglob("*") if path.is_dir()):
        identity = _problem_identity_from_directory(directory)
        if identity is None or directory in seen_directories:
            continue
        external_id, title = identity
        files = [path for path in directory.rglob("*") if path.is_file()]
        code_files = [path for path in files if path.suffix.casefold() in CODE_SUFFIXES]
        markdown = _problem_markdown(directory)
        if not code_files and markdown is None:
            continue
        seen_directories.add(directory)

        body = ""
        if markdown is not None:
            try:
                body = read_text(markdown)
            except (OSError, ValueError) as exc:
                warnings.append(f"{markdown.relative_to(root)}: {exc}")
        source_url_match = LEETCODE_SLUG.search(body)
        source_url = source_url_match.group(0) if source_url_match else None
        key = canonical_problem_key(
            external_id=external_id,
            title=title,
            source_url=source_url,
        )
        source_path = (markdown or directory).relative_to(root).as_posix()
        source_hash = sha256_file(markdown) if markdown is not None else sha256_bytes(key.encode())
        difficulty_match = re.search(
            r"difficulty\s*[:|\-]*\s*(easy|medium|hard)",
            body,
            flags=re.IGNORECASE,
        )
        problems.append(
            ProblemObservation(
                canonical_key=key,
                external_id=external_id,
                title=title,
                slug=slugify(title),
                description=_description_from_markdown(body),
                difficulty=normalize_difficulty(
                    difficulty_match.group(1) if difficulty_match else None
                ),
                source_url=source_url,
                topics=_topics_from_markdown(body),
                source_name=source_name,
                source_path=source_path,
                source_hash=source_hash,
                disposition=disposition,
            )
        )
        time_complexity, space_complexity = complexity_from_markdown(body)
        explanation = body or None
        for code_file in code_files:
            language = LANGUAGE_BY_SUFFIX.get(code_file.suffix.casefold())
            if language is None:
                continue
            try:
                source_code = read_text(code_file, maximum=MAX_CODE_BYTES)
            except (OSError, ValueError) as exc:
                warnings.append(f"{code_file.relative_to(root)}: {exc}")
                continue
            solutions.append(
                SolutionObservation(
                    canonical_key=key,
                    language=language,
                    source_code=source_code,
                    explanation=explanation,
                    time_complexity=time_complexity,
                    space_complexity=space_complexity,
                    source_name=source_name,
                    source_path=code_file.relative_to(root).as_posix(),
                    source_hash=sha256_file(code_file),
                    disposition=disposition,
                )
            )
    return problems, solutions, warnings


def _company_and_window(path: Path, root: Path) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    if len(relative.parts) > 1:
        company = normalize_company(relative.parts[-2])
        stem = path.stem
        for prefix in ("1. ", "2. ", "3. ", "4. ", "5. "):
            stem = stem.removeprefix(prefix)
        return company, slugify(stem)
    match = re.match(
        r"(?P<company>.+?)_(?P<window>6months|1year|2year|alltime)$",
        path.stem,
    )
    if match:
        return normalize_company(match.group("company")), match.group("window")
    return normalize_company(path.stem), None


def _row_value(row: dict[str, str], *names: str) -> str | None:
    normalized = {slugify(key): value for key, value in row.items() if key is not None}
    for name in names:
        value = normalized.get(slugify(name))
        if value is not None and value.strip():
            return value.strip()
    return None


def parse_company_csvs(
    root: Path,
    *,
    source_name: str,
) -> tuple[list[CompanyObservation], list[str]]:
    observations: list[CompanyObservation] = []
    warnings: list[str] = []
    for path in sorted(root.rglob("*.csv")):
        company, window = _company_and_window(path, root)
        try:
            with path.open(
                "r",
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            ) as stream:
                reader = csv.DictReader(stream)
                for row_number, row in enumerate(reader, 2):
                    title = _row_value(row, "title", "problem")
                    if not title:
                        continue
                    external_id = _row_value(
                        row,
                        "id",
                        "problem id",
                        "question id",
                    )
                    url = _row_value(
                        row,
                        "url",
                        "link",
                        "leetcode question link",
                    )
                    difficulty = normalize_difficulty(_row_value(row, "difficulty"))
                    acceptance = parse_number(
                        _row_value(
                            row,
                            "acceptance",
                            "acceptance rate",
                            "acceptance %",
                        )
                    )
                    frequency = parse_number(_row_value(row, "frequency", "frequency %"))
                    topic_text = _row_value(row, "topics", "topic", "tags") or ""
                    topics = tuple(
                        sorted(
                            {
                                normalize_topic(value)
                                for value in topic_text.split(",")
                                if value.strip()
                            }
                        )
                    )
                    key = canonical_problem_key(
                        external_id=external_id,
                        title=title,
                        source_url=url,
                    )
                    observations.append(
                        CompanyObservation(
                            canonical_key=key,
                            external_id=external_id,
                            title=normalize_title(title),
                            problem_url=url,
                            company=company,
                            observation_window=window,
                            difficulty=difficulty,
                            acceptance_rate=acceptance,
                            frequency=frequency,
                            topics=topics,
                            source_name=source_name,
                            source_path=(f"{path.relative_to(root).as_posix()}#{row_number}"),
                            source_hash=sha256_bytes(
                                json.dumps(row, sort_keys=True).encode("utf-8")
                            ),
                        )
                    )
        except (OSError, csv.Error) as exc:
            warnings.append(f"{path.relative_to(root)}: {exc}")
    return observations, warnings


def parse_system_design_notes(
    root: Path,
    *,
    source_name: str,
    disposition: SourceDisposition,
) -> tuple[list[SystemDesignObservation], list[str]]:
    observations: list[SystemDesignObservation] = []
    warnings: list[str] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.casefold() in {"readme.md", "license.md"}:
            continue
        try:
            body = read_text(path)
        except (OSError, ValueError) as exc:
            warnings.append(f"{path.relative_to(root)}: {exc}")
            continue
        headings = tuple(
            normalize_title(match.group("title"))
            for line in body.splitlines()
            if (match := HEADING.match(line))
        )
        title = headings[0] if headings else normalize_title(path.stem)
        image_paths = tuple(
            sorted(
                set(
                    re.findall(
                        r"!\[[^\]]*\]\(([^)]+\.(?:png|jpg|jpeg|webp|svg))\)",
                        body,
                        flags=re.IGNORECASE,
                    )
                )
            )
        )
        observations.append(
            SystemDesignObservation(
                slug=slugify(title),
                title=title,
                body=body,
                headings=headings,
                image_paths=image_paths,
                source_name=source_name,
                source_path=path.relative_to(root).as_posix(),
                source_hash=sha256_file(path),
                disposition=disposition,
            )
        )
    return observations, warnings


def parse_learning_resources(
    root: Path,
    *,
    source_name: str,
    disposition: SourceDisposition,
) -> tuple[list[LearningResourceObservation], list[str]]:
    observations: list[LearningResourceObservation] = []
    warnings: list[str] = []
    supported = CODE_SUFFIXES | {".md", ".txt"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in supported:
            continue
        if _problem_identity_from_directory(path.parent) is not None:
            continue
        try:
            body = read_text(
                path,
                maximum=(
                    MAX_CODE_BYTES if path.suffix.casefold() in CODE_SUFFIXES else MAX_TEXT_BYTES
                ),
            )
        except (OSError, ValueError) as exc:
            warnings.append(f"{path.relative_to(root)}: {exc}")
            continue
        relative = path.relative_to(root)
        language = LANGUAGE_BY_SUFFIX.get(path.suffix.casefold())
        category = slugify(relative.parts[0] if relative.parts else "general")
        title = normalize_title(path.stem)
        observations.append(
            LearningResourceObservation(
                slug=slugify(relative.with_suffix("").as_posix()),
                title=title,
                category=category,
                language=language,
                body=body,
                source_name=source_name,
                source_path=relative.as_posix(),
                source_hash=sha256_file(path),
                disposition=disposition,
            )
        )
    return observations, warnings


def parse_repository(
    root: Path,
    *,
    source_name: str,
    disposition: SourceDisposition = SourceDisposition.RIGHTS_REVIEW_REQUIRED,
) -> IngestionBundle:
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")
    bundle = IngestionBundle(
        source_name=source_name,
        disposition=disposition,
    )
    bundle.files.extend(
        source_file_record(path, root, source_name)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )

    problems, solutions, warnings = parse_problem_directories(
        root,
        source_name=source_name,
        disposition=disposition,
    )
    bundle.problems.extend(problems)
    bundle.solutions.extend(solutions)
    bundle.warnings.extend(warnings)

    companies, warnings = parse_company_csvs(
        root,
        source_name=source_name,
    )
    bundle.companies.extend(companies)
    bundle.warnings.extend(warnings)

    normalized_source_name = source_name.casefold()
    if "system-design" in normalized_source_name or "system design" in normalized_source_name:
        articles, warnings = parse_system_design_notes(
            root,
            source_name=source_name,
            disposition=disposition,
        )
        bundle.system_design.extend(articles)
        bundle.warnings.extend(warnings)

    if "competitive" in normalized_source_name or "awesome" in normalized_source_name:
        resources, warnings = parse_learning_resources(
            root,
            source_name=source_name,
            disposition=disposition,
        )
        bundle.resources.extend(resources)
        bundle.warnings.extend(warnings)

    return bundle


def merge_bundles(bundles: Iterable[IngestionBundle]) -> IngestionBundle:
    merged = IngestionBundle(
        source_name="merged-upload-corpus",
        disposition=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
    )
    problem_map: dict[str, ProblemObservation] = {}
    solution_keys: set[tuple[str, str, str]] = set()
    company_keys: set[tuple[str, str, str | None, str]] = set()
    article_keys: set[tuple[str, str]] = set()
    resource_keys: set[tuple[str, str]] = set()

    for bundle in bundles:
        merged.files.extend(bundle.files)
        merged.warnings.extend(bundle.warnings)
        for problem in bundle.problems:
            existing = problem_map.get(problem.canonical_key)
            if existing is None:
                problem_map[problem.canonical_key] = problem
                continue
            current_description = existing.description or ""
            candidate_description = problem.description or ""
            if len(candidate_description) > len(current_description):
                problem_map[problem.canonical_key] = problem
        for solution in bundle.solutions:
            key = (
                solution.canonical_key,
                solution.language,
                solution.source_hash,
            )
            if key not in solution_keys:
                solution_keys.add(key)
                merged.solutions.append(solution)
        for observation in bundle.companies:
            key = (
                observation.canonical_key,
                observation.company,
                observation.observation_window,
                observation.source_hash,
            )
            if key not in company_keys:
                company_keys.add(key)
                merged.companies.append(observation)
        for article in bundle.system_design:
            key = (article.slug, article.source_hash)
            if key not in article_keys:
                article_keys.add(key)
                merged.system_design.append(article)
        for resource in bundle.resources:
            key = (resource.slug, resource.source_hash)
            if key not in resource_keys:
                resource_keys.add(key)
                merged.resources.append(resource)

    merged.problems = sorted(
        problem_map.values(),
        key=lambda item: item.canonical_key,
    )
    return merged


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
