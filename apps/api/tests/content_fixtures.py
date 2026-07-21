from __future__ import annotations

from copy import deepcopy
from typing import Any


def _base(external_id: str, question_type: str, track: str, title: str) -> dict[str, Any]:
    source_hash = "sha256:" + external_id.casefold().encode().hex()[:64].ljust(64, "0")
    return {
        "id": external_id,
        "version": "1.0.0",
        "title": title,
        "slug": f"{external_id.casefold()}-{title.casefold().replace(' ', '-')}",
        "question_type": question_type,
        "primary_track": track,
        "secondary_skills": ["deterministic-reasoning", "edge-case-analysis"],
        "difficulty": "advanced",
        "difficulty_dimensions": {
            "conceptual": 3,
            "implementation": 3,
            "scale": 3,
            "ambiguity": 3,
            "prerequisite_depth": 3,
        },
        "role_level": "senior",
        "company_style_tags": [],
        "learning_objectives": ["Produce a deterministic result and explain edge cases."],
        "prerequisites": ["General software engineering fundamentals"],
        "estimated_duration_minutes": 50,
        "public_problem_statement": "Solve this independently authored operational scenario.",
        "candidate_instructions": ["Clarify assumptions before implementing or designing."],
        "interviewer_instructions": ["Probe correctness, trade-offs, and failure handling."],
        "constraints": ["All supplied identifiers are non-empty strings."],
        "assumptions": ["Input records are JSON-compatible."],
        "expected_clarifying_questions": ["How should ties be resolved?"],
        "hints": [],
        "rubric": {
            "dimensions": [
                {
                    "name": "Correctness",
                    "description": "Meets the stated behavior and handles boundaries.",
                    "weight": 50,
                    "evidence_required": ["Automated tests or explicit design evidence"],
                    "strong_indicators": ["All invariants are explicit"],
                    "weak_indicators": ["Relies on unspecified behavior"],
                },
                {
                    "name": "Engineering judgment",
                    "description": "Explains complexity, failure modes, and alternatives.",
                    "weight": 50,
                    "evidence_required": ["Trade-off discussion"],
                    "strong_indicators": ["Connects choices to requirements"],
                    "weak_indicators": ["Presents one option without trade-offs"],
                },
            ],
            "score_bands": {
                "strong": "Correct, tested, and production-aware.",
                "developing": "Partially correct with material omissions.",
            },
        },
        "reference_solution": {
            "content": "Reference solution supplied by the type-specific fixture.",
            "explanation": "The reference follows the deterministic contract.",
            "alternatives": [],
            "trade_offs": ["Favor explicit behavior over implicit arrival ordering."],
            "debugging_notes": ["Inspect the smallest failing boundary case first."],
        },
        "alternative_solutions": [],
        "common_mistakes": ["Using arrival order as event truth."],
        "follow_up_questions": ["How would this operate under retries at scale?"],
        "easier_variants": ["Inputs arrive in canonical order."],
        "harder_variants": ["Inputs arrive concurrently from multiple regions."],
        "related_question_ids": [],
        "author": {"id": "local-author", "display_name": "Avery Author"},
        "reviewers": [],
        "license": {
            "rights_basis": "original",
            "license_identifier": "RIGOR-ORIGINAL-1.0",
            "certification": "I certify this question is independently authored.",
            "evidence": ["Authorship trace retained by the platform."],
        },
        "provenance": {
            "originality_statement": "Independently authored from general engineering concepts.",
            "authoring_method": "Human-directed original scenario and deterministic fixtures.",
            "source_classes": ["general engineering knowledge"],
            "source_notes": ["No proprietary or restricted question source was used."],
            "source_content_hash": source_hash,
            "certification_evidence": ["Author declaration and source-control history"],
        },
        "source_content_hash": source_hash,
        "created_at": "2026-07-20T12:00:00Z",
        "updated_at": "2026-07-20T12:00:00Z",
        "publication_status": "imported",
    }


def python_question(external_id: str = "PY-9101") -> dict[str, Any]:
    question = _base(
        external_id,
        "python_coding",
        "python-engineering",
        "Reconcile Out-of-Order Device Counters",
    )
    solution = """def solve(payload):
    latest = {}
    for reading in payload:
        device = reading["device"]
        candidate = (reading["sequence"], reading["value"])
        current = latest.get(device)
        if current is None or candidate[0] > current[0]:
            latest[device] = candidate
    return [[device, latest[device][1]] for device in sorted(latest)]
"""
    tests = [
        {
            "id": "PY-9101-P01",
            "name": "keeps latest sequence per device",
            "visibility": "public",
            "input": [
                {"device": "b", "sequence": 1, "value": 7},
                {"device": "a", "sequence": 2, "value": 9},
                {"device": "a", "sequence": 1, "value": 4},
            ],
            "expected_output": [["a", 9], ["b", 7]],
        },
        {
            "id": "PY-9101-P02",
            "name": "handles empty input",
            "visibility": "public",
            "input": [],
            "expected_output": [],
        },
        {
            "id": "PY-9101-P03",
            "name": "handles one device",
            "visibility": "public",
            "input": [{"device": "sensor", "sequence": 5, "value": -2}],
            "expected_output": [["sensor", -2]],
        },
        {
            "id": "PY-9101-H01",
            "name": "ignores several delayed values",
            "visibility": "hidden",
            "input": [
                {"device": "x", "sequence": 10, "value": 1},
                {"device": "x", "sequence": 2, "value": 99},
                {"device": "x", "sequence": 9, "value": 50},
            ],
            "expected_output": [["x", 1]],
        },
    ]
    question["reference_solution"] = {
        **question["reference_solution"],
        "content": solution,
        "complexity": {
            "expected_time": "O(n + d log d)",
            "expected_space": "O(d)",
            "explanation": "One pass tracks d devices and sorting stabilizes output order.",
        },
    }
    question["type_specification"] = {
        "runtime": "3.13",
        "input_specification": "A list of device, sequence, and integer value records.",
        "output_specification": "Device/value pairs sorted by device.",
        "starter_code": "def solve(payload):\n    ...",
        "tests": tests,
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "expected_complexity": {
            "expected_time": "O(n + d log d)",
            "expected_space": "O(d)",
            "explanation": "Track one latest record per device and sort the result.",
        },
        "production_variation": "Consume retrying device batches with durable checkpoints.",
    }
    return question


def sql_question(external_id: str = "SQL-9101") -> dict[str, Any]:
    question = _base(
        external_id,
        "sql_coding",
        "sql-analytics",
        "Detect Stale Pipeline Checkpoints",
    )
    setup = [
        "CREATE TABLE checkpoints (pipeline text PRIMARY KEY, "
        "observed_at integer NOT NULL, expected_by integer NOT NULL)",
        "INSERT INTO checkpoints VALUES ('orders', 80, 100), "
        "('billing', 110, 100), ('catalog', 90, 90)",
    ]
    reference_sql = (
        "SELECT pipeline, expected_by - observed_at AS delay "
        "FROM checkpoints WHERE observed_at < expected_by ORDER BY pipeline"
    )
    question["reference_solution"] = {
        **question["reference_solution"],
        "content": reference_sql,
    }
    question["type_specification"] = {
        "dialect": "postgresql18",
        "business_scenario": "A data platform needs a deterministic stale-checkpoint report.",
        "schema_diagram_description": "One checkpoint row per pipeline.",
        "ddl": setup[0],
        "seed_sql": setup[1],
        "expected_output_columns": ["pipeline", "delay"],
        "tests": [
            {
                "id": "SQL-9101-P01",
                "name": "reports stale pipelines",
                "visibility": "public",
                "input": {"setup_sql": setup},
                "expected_output": [["orders", 20]],
            },
            {
                "id": "SQL-9101-H01",
                "name": "reports multiple stale pipelines",
                "visibility": "hidden",
                "input": {
                    "setup_sql": [
                        setup[0],
                        "INSERT INTO checkpoints VALUES ('zeta', 1, 4), ('alpha', 2, 8)",
                    ]
                },
                "expected_output": [["alpha", 6], ["zeta", 3]],
            },
        ],
        "reference_sql": reference_sql,
        "suggested_indexes": [
            "The primary key supports stable identity; no extra index is needed here."
        ],
        "execution_plan_discussion": (
            "At scale, a partial index on stale candidates is useful only if freshness "
            "values are materialized and maintained safely."
        ),
        "statement_timeout_ms": 2000,
    }
    return question


def system_design_question(external_id: str = "SD-9101") -> dict[str, Any]:
    question = _base(
        external_id,
        "system_design",
        "system-design",
        "Design a Regional Safety-Notice Router",
    )
    question["difficulty"] = "staff"
    question["role_level"] = "staff"
    question["difficulty_dimensions"] = {
        "conceptual": 4,
        "implementation": 2,
        "scale": 4,
        "ambiguity": 4,
        "prerequisite_depth": 4,
    }
    question["type_specification"] = {
        "interviewer_only_context": (
            "The system replaces three regional tools without interrupting emergency notices."
        ),
        "functional_requirements": ["Route verified notices to subscribed regional channels."],
        "non_functional_requirements": ["Deliver 99.99% within 30 seconds."],
        "out_of_scope": ["Authoring notice content"],
        "scale_assumptions": ["20 million recipients; 100 notices/day; 10x emergency peak."],
        "capacity_calculation": (
            "At 20M recipients and 1KB delivery envelope, a global emergency creates "
            "20GB before replication; draining in 10 minutes requires about 33k "
            "deliveries/s plus regional headroom."
        ),
        "api_design": ["POST /notices with idempotency key", "GET /deliveries/{id}"],
        "data_model": ["Notice", "RecipientSubscription", "DeliveryAttempt", "RegionalPolicy"],
        "architecture": {
            "nodes": [
                {"id": "gateway", "label": "Notice gateway", "kind": "service"},
                {"id": "policy", "label": "Regional policy", "kind": "service"},
                {"id": "bus", "label": "Durable delivery log", "kind": "event_bus"},
                {"id": "workers", "label": "Regional workers", "kind": "compute"},
            ],
            "edges": [
                {"source": "gateway", "target": "policy", "label": "authorize"},
                {"source": "policy", "target": "bus", "label": "append"},
                {"source": "bus", "target": "workers", "label": "consume"},
            ],
            "groups": ["control plane", "regional delivery plane"],
            "trust_boundaries": ["public administration to controlled gateway"],
            "data_flows": ["Signed notice to policy decision to partitioned delivery stream."],
            "failure_domains": ["region", "provider channel", "event partition"],
            "annotations": ["All writes carry stable idempotency keys."],
        },
        "architecture_explanation": (
            "A small global control plane validates notices before durable regional fan-out."
        ),
        "request_data_flow": [
            "Authenticate",
            "validate policy",
            "append once",
            "fan out",
            "record outcome",
        ],
        "storage_analysis": (
            "Relational control metadata pairs with an append-only delivery log and compact "
            "outcome store."
        ),
        "partition_strategy": "Partition delivery work by region and stable recipient hash.",
        "cache_strategy": (
            "Cache versioned regional policy with short bounded staleness and emergency "
            "invalidation."
        ),
        "consistency_model": (
            "Strong notice authorization; at-least-once delivery with idempotent provider calls."
        ),
        "reliability_plan": (
            "Replay durable partitions and isolate failing delivery providers with "
            "circuit breakers."
        ),
        "failure_scenarios": [
            "Regional outage",
            "provider throttling",
            "duplicate emergency submission",
        ],
        "disaster_recovery": (
            "Replicate control state and retain encrypted delivery logs for replay."
        ),
        "multi_region_strategy": (
            "Home notices to two control regions and deliver from recipient-local workers."
        ),
        "security": ["Hardware-backed signing keys", "least-privilege operator roles"],
        "privacy": ["Minimize recipient attributes in the delivery stream"],
        "abuse_prevention": ["Four-eyes emergency approval and rate anomalies"],
        "observability": ["End-to-end delivery SLO by region and provider"],
        "deployment": "Migrate one region at a time with mirrored delivery outcomes.",
        "cost_considerations": ["Emergency idle capacity versus provider burst commitments"],
        "build_versus_buy": (
            "Buy commodity channel delivery but retain policy, audit, and routing control."
        ),
        "migration_plan": (
            "Shadow traffic, compare outcomes, then move regional authorities behind "
            "reversible flags."
        ),
        "alternative_designs": ["Fully regional control planes with asynchronous global audit"],
        "trade_offs": ["Global policy consistency increases control-plane dependency."],
        "interview_follow_up_tree": {
            "baseline": ["Introduce a region outage"],
            "strong": ["Ask for migration governance"],
        },
        "requirement_changes": ["Require sovereign in-region recipient data"],
    }
    return question


def malformed_unknown_field() -> dict[str, Any]:
    payload = deepcopy(python_question("PY-9199"))
    payload["copied_proprietary_source"] = "restricted"
    return payload
