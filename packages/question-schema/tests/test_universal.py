from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from rigor_question_schema.universal import universal_question_adapter


def minimal_python_question() -> dict[str, object]:
    source_hash = "sha256:" + "a" * 64
    return {
        "id": "PY-9001",
        "version": "1.0.0",
        "title": "Reconcile Delayed Sensor Updates",
        "slug": "reconcile-delayed-sensor-updates",
        "question_type": "python_coding",
        "primary_track": "python-engineering",
        "secondary_skills": ["hash-maps"],
        "difficulty": "intermediate",
        "difficulty_dimensions": {
            "conceptual": 2,
            "implementation": 3,
            "scale": 2,
            "ambiguity": 2,
            "prerequisite_depth": 2,
        },
        "role_level": "senior",
        "company_style_tags": [],
        "learning_objectives": ["Reconcile out-of-order updates deterministically."],
        "prerequisites": ["Python mappings"],
        "estimated_duration_minutes": 45,
        "public_problem_statement": "Implement an original sensor-update reconciliation function.",
        "candidate_instructions": ["Define solve(payload)."],
        "interviewer_instructions": ["Probe timestamp tie handling."],
        "constraints": ["Inputs are JSON-compatible."],
        "assumptions": ["Sequence IDs are unique per sensor."],
        "expected_clarifying_questions": ["How are ties resolved?"],
        "hints": [],
        "rubric": {
            "dimensions": [
                {
                    "name": "Correctness",
                    "description": "Produces the required state.",
                    "weight": 100,
                    "evidence_required": ["tests"],
                    "strong_indicators": ["all cases pass"],
                    "weak_indicators": ["order-dependent result"],
                }
            ],
            "score_bands": {"strong": "Correct and well explained."},
        },
        "reference_solution": {
            "content": "def solve(payload):\n    return payload",
            "explanation": "The fixture focuses on schema discrimination.",
            "alternatives": [],
            "trade_offs": [],
            "debugging_notes": [],
        },
        "alternative_solutions": [],
        "common_mistakes": ["Using arrival order."],
        "follow_up_questions": ["How would this stream at scale?"],
        "easier_variants": ["Inputs arrive in order."],
        "harder_variants": ["Add tombstones."],
        "related_question_ids": [],
        "author": {"id": "author-1", "display_name": "Original Author"},
        "reviewers": [],
        "license": {
            "rights_basis": "original",
            "license_identifier": "RIGOR-ORIGINAL-1.0",
            "certification": "I certify this package is independently authored.",
            "evidence": ["Authorship trace retained."],
        },
        "provenance": {
            "originality_statement": "Independently authored for this platform.",
            "authoring_method": "Human-directed original drafting.",
            "source_classes": ["general engineering knowledge"],
            "source_notes": ["No proprietary source used."],
            "source_content_hash": source_hash,
            "certification_evidence": ["Draft trace"],
        },
        "source_content_hash": source_hash,
        "created_at": "2026-07-20T12:00:00Z",
        "updated_at": "2026-07-20T12:00:00Z",
        "publication_status": "generated",
        "type_specification": {
            "runtime": "3.13",
            "input_specification": "A JSON-compatible payload.",
            "output_specification": "A JSON-compatible result.",
            "starter_code": "def solve(payload):\n    ...",
            "tests": [
                {
                    "id": "P1",
                    "name": "public one",
                    "visibility": "public",
                    "input": 1,
                    "expected_output": 1,
                },
                {
                    "id": "P2",
                    "name": "public two",
                    "visibility": "public",
                    "input": 2,
                    "expected_output": 2,
                },
                {
                    "id": "P3",
                    "name": "public three",
                    "visibility": "public",
                    "input": 3,
                    "expected_output": 3,
                },
                {
                    "id": "H1",
                    "name": "hidden",
                    "visibility": "hidden",
                    "input": 4,
                    "expected_output": 4,
                },
            ],
            "time_limit_ms": 1000,
            "memory_limit_mb": 128,
            "expected_complexity": {
                "expected_time": "O(1)",
                "expected_space": "O(1)",
                "explanation": "Fixture only.",
            },
            "production_variation": "Process updates from a durable stream.",
        },
    }


def test_question_type_discriminates_and_unknown_fields_are_rejected() -> None:
    parsed = universal_question_adapter.validate_python(minimal_python_question())
    assert parsed.question_type == "python_coding"
    malformed = deepcopy(minimal_python_question())
    malformed["copied_from"] = "unauthorized-source"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        universal_question_adapter.validate_python(malformed)


def test_missing_rights_evidence_is_rejected() -> None:
    malformed = deepcopy(minimal_python_question())
    malformed["license"]["evidence"] = []  # type: ignore[index]
    with pytest.raises(ValidationError):
        universal_question_adapter.validate_python(malformed)
