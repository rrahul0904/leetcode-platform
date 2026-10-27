#!/usr/bin/env python3
"""Offline, fail-closed importer for user-owned Level 4 DE assessment DOCX files.

Candidate material and private interviewer-only solutions are emitted into separate
directories. Outputs require human review; they are NOT automatically published.
This script must run only in an access-controlled ingestion workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SECTIONS = {"A": "python", "B": "sql", "C": "pyspark", "D": "snowflake"}
MARKS = {1: 10, 2: 10, 3: 8, 4: 8, 5: 9, 6: 15, **{k: 4 for k in range(7, 17)}}
TIME = {1: 6, 2: 6, 3: 6, 4: 6, 5: 6, 6: 8, **{k: 2.2 for k in range(7, 17)}}
CANDIDATE_PATTERN = "Level4_Data_Engineering_Interview_Set_{n}_Candidate.docx"
GUIDE_PATTERN = "Level4_Data_Engineering_Set_{n}_Solution_Guide.docx"


def _text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{W}t")).strip()


def _read_docx(path: Path) -> tuple[list[str], list[list[list[str]]]]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    body = ET.fromstring(xml).find(f"{W}body")
    if body is None:
        raise ValueError(f"Missing document body: {path.name}")
    paragraphs: list[str] = []
    tables: list[list[list[str]]] = []
    for element in body:
        if element.tag == f"{W}p":
            value = _text(element)
            if value:
                paragraphs.append(value)
        elif element.tag == f"{W}tbl":
            tables.append([
                [_text(cell) for cell in row.findall(f"{W}tc")]
                for row in element.findall(f"{W}tr")
            ])
    return paragraphs, tables


def _candidate_questions(paragraphs: list[str], set_number: int) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section = ""
    for paragraph in paragraphs:
        section_match = re.match(r"SECTION ([A-D])\s*-", paragraph, re.I)
        if section_match:
            section = SECTIONS[section_match.group(1).upper()]
            current = None
            continue
        written = re.match(r"Question ([1-6])\s*-\s*(.+?)\s*\[", paragraph)
        mcq = re.match(r"(1[0-6]|[7-9])\.\s+(.+)", paragraph)
        if written or mcq:
            if written is not None:
                number, prompt = int(written.group(1)), written.group(2)
            elif mcq is not None:
                number, prompt = int(mcq.group(1)), mcq.group(2)
            else:
                raise AssertionError("Unreachable: question matched neither format")
            expected = (
                "python" if number <= 2 else
                "sql" if number <= 5 else
                "pyspark" if number == 6 else "snowflake"
            )
            if section != expected:
                raise ValueError(f"Set {set_number} Q{number} in wrong section")
            current = {
                "id": f"l4-de-s{set_number}-q{number:02d}",
                "number": number,
                "section": section,
                "type": "multiple_choice" if number >= 7 else "written",
                "marks": MARKS[number],
                "recommended_minutes": TIME[number],
                "prompt": prompt.strip(),
                "details": [],
                "options": [],
            }
            questions.append(current)
            continue
        if current is None:
            continue
        if paragraph.startswith("End of paper:"):
            current = None
            continue
        option = re.match(r"^([A-D])\.\s+(.+)", paragraph)
        if option and current["type"] == "multiple_choice":
            current["options"].append({"key": option.group(1), "text": option.group(2)})
        elif paragraph != "Requirements":
            current["details"].append(paragraph)
    if [q["number"] for q in questions] != list(range(1, 17)):
        raise ValueError(f"Set {set_number} has missing, duplicate or out-of-order questions")
    if any(len(q["options"]) != 4 for q in questions[6:]):
        raise ValueError(f"Set {set_number} has incomplete multiple-choice options")
    if sum(q["marks"] for q in questions) != 100:
        raise ValueError(f"Set {set_number} has invalid mark total")
    return questions


def _guide_answers(tables: list[list[list[str]]], set_number: int) -> dict[str, str]:
    answers: dict[str, str] = {}
    for table in tables:
        for row in table:
            if len(row) >= 2 and re.fullmatch(r"(?:[7-9]|1[0-6])", row[0].strip()):
                key, answer = row[0].strip(), row[1].strip()
                if key in answers or answer not in {"A", "B", "C", "D"}:
                    raise ValueError(f"Set {set_number} duplicate/invalid answer Q{key}")
                answers[key] = answer
    if set(answers) != {str(k) for k in range(7, 17)}:
        raise ValueError(f"Set {set_number} missing interviewer answer keys")
    return answers


def ingest(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    candidate_dir = output_dir / "candidate_review_only"
    private_dir = output_dir / "private_interviewer_only"
    if candidate_dir.resolve() == private_dir.resolve():
        raise ValueError("Candidate and interviewer output must remain separate")
    candidate_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    catalog: dict[str, Any] = {"schema_version": 1, "publication_state": "review_required", "sets": []}
    for number in range(3, 10):
        candidate_path = input_dir / CANDIDATE_PATTERN.format(n=number)
        guide_path = input_dir / GUIDE_PATTERN.format(n=number)
        paragraphs, _ = _read_docx(candidate_path)
        guide_paragraphs, guide_tables = _read_docx(guide_path)
        questions = _candidate_questions(paragraphs, number)
        key = _guide_answers(guide_tables, number)
        assessment = {
            "schema_version": 1,
            "id": f"l4-de-set-{number}",
            "level": 4,
            "title": f"Level 4 Data Engineering - Set {number}",
            "duration_minutes": 60,
            "maximum_marks": 100,
            "sections": {"python": 20, "sql": 25, "pyspark": 15, "snowflake": 40},
            "publication_state": "review_required",
            "questions": questions,
            "candidate_source_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        }
        interviewer = {
            "schema_version": 1,
            "assessment_id": assessment["id"],
            "visibility": "interviewer_only",
            "guide_source_sha256": hashlib.sha256(guide_path.read_bytes()).hexdigest(),
            "mcq_answers": key,
            "full_solution_guide_paragraphs": guide_paragraphs,
            "warning": "Human review required; never serve through candidate frontend or routes.",
        }
        (candidate_dir / f"set-{number}.json").write_text(
            json.dumps(assessment, indent=2) + "\n", encoding="utf-8"
        )
        (private_dir / f"set-{number}.json").write_text(
            json.dumps(interviewer, indent=2) + "\n", encoding="utf-8"
        )
        catalog["sets"].append({
            "id": assessment["id"], "question_count": len(questions),
            "maximum_marks": 100, "duration_minutes": 60,
            "candidate_file": f"set-{number}.json", "requires_human_review": True,
        })
    (candidate_dir / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    catalog = ingest(args.input_dir, args.output_dir)
    print(
        f"STAGED (NOT PUBLISHED): {len(catalog['sets'])} sets, "
        f"{sum(row['question_count'] for row in catalog['sets'])} questions; "
        "solution guides separated"
    )


if __name__ == "__main__":
    main()
