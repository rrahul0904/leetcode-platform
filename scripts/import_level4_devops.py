#!/usr/bin/env python3
"""Stage private Level-4 DevOps DOCX assessments; NEVER auto-publish source materials."""

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
CANDIDATE = "DevOps_Level4_60min_Set_{n:02d}_Candidate_Questions.docx"
INTERVIEWER = "DevOps_Level4_60min_Set_{n:02d}_Interviewer_Solutions.docx"
SECTIONS = {"A": "advanced-python", "B": "production-scenarios", "C": "devops-mcq"}


def read_docx(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    body = ET.fromstring(xml).find(f"{W}body")
    if body is None:
        raise ValueError(f"Missing document body: {path.name}")
    paragraphs: list[str] = []
    for p in body.findall(f"{W}p"):
        value = "".join(node.text or "" for node in p.iter(f"{W}t")).strip()
        if value:
            paragraphs.append(value)
    return paragraphs


def parse_candidate(paragraphs: list[str], set_number: int) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section = ""
    for paragraph in paragraphs:
        section_match = re.match(r"SECTION ([A-C])\s*[–-]", paragraph, re.I)
        if section_match:
            section = SECTIONS[section_match.group(1).upper()]
            current = None
            continue
        written = re.match(
            r"Question ([1-4])\s*[–-]\s*(.+?)\s*\[(\d+) marks\]", paragraph
        )
        mcq = re.fullmatch(r"Question (1[0-4]|[5-9])\s*\[(\d+) marks\]", paragraph)
        if written or mcq:
            if written:
                number, title, marks = (
                    int(written.group(1)), written.group(2), int(written.group(3))
                )
            elif mcq:
                number, title, marks = int(mcq.group(1)), "", int(mcq.group(2))
            else:
                raise AssertionError("No question match")
            expected = (
                "advanced-python" if number < 3 else
                "production-scenarios" if number < 5 else "devops-mcq"
            )
            if section != expected or marks != (4 if number >= 5 else 15):
                raise ValueError(f"Invalid section/marks: set {set_number} Q{number}")
            current = {
                "id": f"l4-devops-s{set_number:02d}-q{number:02d}",
                "number": number,
                "section": section,
                "type": "multiple_choice" if number >= 5 else "written",
                "marks": marks,
                "prompt": title,
                "details": [],
                "options": [],
            }
            questions.append(current)
            continue
        if paragraph.startswith("End of paper:"):
            current = None
        if current is None or paragraph == "Requirements":
            continue
        option = re.match(r"^([A-D])\.\s+(.+)", paragraph)
        if option and current["type"] == "multiple_choice":
            current["options"].append({"key": option.group(1), "text": option.group(2)})
        elif current["type"] == "multiple_choice" and not current["prompt"]:
            current["prompt"] = paragraph
        else:
            current["details"].append(paragraph)
    if [q["number"] for q in questions] != list(range(1, 15)):
        raise ValueError(f"Set {set_number}: expected 14 unique, ordered questions")
    for question in questions:
        if not question["prompt"]:
            raise ValueError(f"Set {set_number}: empty prompt in Q{question['number']}")
        if question["number"] >= 5 and [
            option["key"] for option in question["options"]
        ] != ["A", "B", "C", "D"]:
            raise ValueError(f"Set {set_number}: missing MCQ options in Q{question['number']}")
    if sum(q["marks"] for q in questions) != 100:
        raise ValueError(f"Set {set_number}: expected 100 marks")
    return questions


def parse_interviewer_key(paragraphs: list[str], set_number: int) -> dict[str, str]:
    in_answers = False
    number: int | None = None
    result: dict[str, str] = {}
    for paragraph in paragraphs:
        if paragraph.startswith("SECTION C"):
            in_answers = True
            continue
        if not in_answers:
            continue
        if paragraph.startswith("INTERVIEWER DECISION GUIDE"):
            break
        question = re.fullmatch(r"Question (1[0-4]|[5-9])", paragraph)
        if question:
            number = int(question.group(1))
            continue
        answer = re.match(r"Correct answer:\s*([A-D])\.\s*.+", paragraph)
        if answer:
            if number is None or not 5 <= number <= 14 or str(number) in result:
                raise ValueError(f"Set {set_number}: invalid/duplicate MCQ answer")
            result[str(number)] = answer.group(1)
    if set(result) != {str(n) for n in range(5, 15)}:
        raise ValueError(f"Set {set_number}: incomplete interviewer key")
    return result


def ingest(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output = output_dir.resolve()
    if input_dir.resolve() == output or any(
        name in {"public", ".git", "apps", "content"} for name in output.parts
    ):
        raise ValueError("Use private staging outside repository and web directories")
    candidate_dir = output / "candidate_review_only"
    private_dir = output / "private_interviewer_only"
    pending: list[tuple[str, str, str]] = []
    records: list[dict[str, Any]] = []
    for number in range(1, 11):
        source = input_dir / CANDIDATE.format(n=number)
        guide = input_dir / INTERVIEWER.format(n=number)
        questions = parse_candidate(read_docx(source), number)
        guide_text = read_docx(guide)
        key = parse_interviewer_key(guide_text, number)
        identifier = f"l4-devops-set-{number:02d}"
        candidate = {
            "schema_version": 1,
            "id": identifier,
            "title": f"Level 4 DevOps - Set {number:02d}",
            "level": 4,
            "duration_minutes": 60,
            "maximum_marks": 100,
            "sections": {
                "advanced-python": 30,
                "production-scenarios": 30,
                "devops-mcq": 40,
            },
            "publication_state": "review_required",
            "candidate_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "questions": questions,
        }
        interviewer = {
            "schema_version": 1,
            "assessment_id": identifier,
            "visibility": "interviewer_only",
            "guide_source_sha256": hashlib.sha256(guide.read_bytes()).hexdigest(),
            "mcq_answers": key,
            "full_solution_guide_paragraphs": guide_text,
        }
        pending.append((
            f"set-{number:02d}.json",
            json.dumps(candidate, indent=2),
            json.dumps(interviewer, indent=2),
        ))
        records.append({
            "id": identifier,
            "question_count": 14,
            "maximum_marks": 100,
            "duration_minutes": 60,
            "publication_state": "review_required",
        })
    # Validate all ten candidate/solution pairs before writing any data.
    candidate_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    for filename, candidate, interviewer in pending:
        (candidate_dir / filename).write_text(candidate + "\n", encoding="utf-8")
        solution_path = private_dir / filename
        solution_path.write_text(interviewer + "\n", encoding="utf-8")
        solution_path.chmod(0o600)
    catalog: dict[str, Any] = {
        "schema_version": 1,
        "publication_state": "review_required",
        "sets": records,
    }
    (candidate_dir / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    catalog = ingest(options.input_dir, options.output_dir)
    print(f"STAGED, NOT PUBLISHED: {len(catalog['sets'])} sets / 140 questions")


if __name__ == "__main__":
    main()
