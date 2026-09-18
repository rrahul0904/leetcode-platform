#!/usr/bin/env python3
"""Promote locally prechecked SQL attachment questions after PostgreSQL family proof.

The execution-bank builder intentionally stops SQL at a conservative local
relational precheck. This stage requires an explicit allow-list of PostgreSQL-
confirmed DDL/reference-query family fingerprints, creates distinct public and
hidden datasets, evaluates the trusted reference query for both, and marks only
those rows runtime-validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


def family_fingerprint(ddl: str, query: str) -> str:
    payload = ddl.strip() + "\n" + query.strip()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def partition_column(query: str) -> str | None:
    match = re.search(r"\bPARTITION\s+BY\s+([A-Za-z_]\w*)", query, flags=re.I)
    return match.group(1) if match else None


def hidden_seed(column: str) -> str:
    rows = [
        (1, 1, 1, "2024-01-01", 1, "old-a"),
        (2, 1, 2, "2024-01-02", 2, "new-a"),
        (3, 2, 3, "2024-01-01", 1, "old-b"),
        (4, 2, 4, "2024-01-03", 3, "new-b"),
        (5, 3, 5, "2024-01-02", 1, "old-c"),
        (6, 3, 6, "2024-01-02", 2, "new-c"),
    ]
    values = ",\n".join(
        "("
        + ",".join(
            str(value)
            if isinstance(value, int)
            else "'" + value.replace("'", "''") + "'"
            for value in row
        )
        + ")"
        for row in rows
    )
    return (
        f'INSERT INTO "facts" '
        f'("fact_id","{column}","category_id","event_ts","ingest_seq","region") '
        f"VALUES {values};"
    )


def query_rows(ddl: str, seed: str, query: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(ddl + "\n" + seed)
        cursor = connection.execute(query.rstrip(";"))
        columns = [description[0] for description in cursor.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    confirmed = set(config.get("confirmed_family_fingerprints", []))
    promoted = 0
    skipped = 0
    family_counts: dict[str, int] = {}
    output_rows: list[dict[str, Any]] = []
    for line in args.input.open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        pending_sql = (
            row.get("subject") == "SQL"
            and row.get("execution_validation_status")
            == "postgres_confirmation_pending"
        )
        if not pending_sql:
            output_rows.append(row)
            continue
        mode = row.get("mode_specification")
        if not isinstance(mode, dict):
            skipped += 1
            output_rows.append(row)
            continue
        challenge = mode.get("challenge")
        if not isinstance(challenge, dict):
            skipped += 1
            output_rows.append(row)
            continue
        ddl = str(challenge.get("ddl") or "")
        public_seed = str(challenge.get("seed_data") or "")
        query = str(mode.get("reference_sql") or "")
        fingerprint = family_fingerprint(ddl, query)
        if fingerprint not in confirmed:
            skipped += 1
            output_rows.append(row)
            continue
        partition = partition_column(query)
        if not partition:
            skipped += 1
            output_rows.append(row)
            continue
        hidden = hidden_seed(partition)
        try:
            public_expected = query_rows(ddl, public_seed, query)
            hidden_expected = query_rows(ddl, hidden, query)
        except sqlite3.Error:
            skipped += 1
            output_rows.append(row)
            continue
        mode.update(
            {
                "schema_sql": ddl,
                "seed_sql": public_seed,
                "starter_code": str(
                    mode.get("starter_sql")
                    or "-- Write your PostgreSQL 18 query here.\n"
                ),
                "statement_timeout_ms": 5000,
                "tests": [
                    {
                        "id": "public-1",
                        "name": "Public dataset",
                        "visibility": "public",
                        "input": None,
                        "expected_output": public_expected,
                        "comparison": "sql_unordered",
                    },
                    {
                        "id": "hidden-1",
                        "name": "Hidden duplicate-key dataset",
                        "visibility": "hidden",
                        "input": {"seed_sql": hidden},
                        "expected_output": hidden_expected,
                        "comparison": "sql_unordered",
                    },
                ],
                "postgres_family_fingerprint": fingerprint,
                "postgres_validation": config.get(
                    "validator", "postgresql-family-confirmation-v1"
                ),
            }
        )
        row["mode_specification"] = mode
        row["runnable"] = True
        row["execution_validation_status"] = "reference_validated"
        family_counts[fingerprint] = family_counts.get(fingerprint, 0) + 1
        promoted += 1
        output_rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in output_rows:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    report = {
        "input_rows": len(output_rows),
        "postgres_confirmed_sql_promoted": promoted,
        "sql_pending_skipped": skipped,
        "confirmed_family_counts": family_counts,
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "policy": (
            "SQL becomes runnable only after explicit PostgreSQL family confirmation "
            "plus distinct public/hidden fixture evaluation."
        ),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if skipped == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
