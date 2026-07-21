#!/usr/bin/env python3
"""Idempotently seed deterministic taxonomy from the canonical manifest."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://rigor:rigor_local_only@localhost:5434/rigor"

DISCOVERED_SOURCES = [
    ("LeetCode", "leetcode.com", "coding-platform"),
    ("HackerRank", "hackerrank.com", "coding-platform"),
    ("NeetCode", "neetcode.io", "curriculum-reference"),
    ("CodeSignal", "codesignal.com", "coding-platform"),
    ("Codewars", "codewars.com", "coding-platform"),
    ("DataLemur", "datalemur.com", "sql-platform"),
    ("StrataScratch", "stratascratch.com", "sql-platform"),
    ("Interview Query", "interviewquery.com", "sql-platform"),
    ("GeeksforGeeks", "geeksforgeeks.org", "technical-reference"),
    ("InterviewBit", "interviewbit.com", "coding-platform"),
    ("Exercism", "exercism.org", "open-practice-platform"),
    ("Project Euler", "projecteuler.net", "mathematics-archive"),
    ("Stack Overflow", "stackoverflow.com", "discussion-reference"),
    ("Stack Exchange", "stackexchange.com", "discussion-reference"),
    ("Reddit", "reddit.com", "public-discussion"),
    ("GitHub", "github.com", "repository-host"),
    ("GitLab", "gitlab.com", "repository-host"),
]

COMPETENCIES = [
    ("algorithms", "Algorithms"),
    ("data-structures", "Data structures"),
    ("python-engineering", "Python engineering"),
    ("sql", "SQL"),
    ("databases", "Databases"),
    ("data-modeling", "Data modeling"),
    ("data-architecture", "Data architecture"),
    ("distributed-systems", "Distributed systems"),
    ("backend-engineering", "Backend engineering"),
    ("system-design", "System design"),
    ("networking", "Networking"),
    ("operating-systems", "Operating systems"),
    ("cloud-infrastructure", "Cloud infrastructure"),
    ("security", "Security"),
    ("reliability", "Reliability"),
    ("observability", "Observability"),
    ("machine-learning", "Machine learning"),
    ("recommendation-systems", "Recommendation systems"),
    ("experimentation", "Experimentation"),
    ("generative-ai", "Generative AI"),
    ("ai-infrastructure", "AI infrastructure"),
    ("ai-evaluation", "AI evaluation"),
    ("ai-safety", "AI safety"),
    ("technical-leadership", "Technical leadership"),
    ("engineering-management", "Engineering management"),
    ("behavioral-competencies", "Behavioral competencies"),
    ("staff-engineering", "Staff engineering"),
    ("principal-engineering", "Principal engineering"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("RIGOR_SEED_DATABASE_URL", DEFAULT_URL))
    args = parser.parse_args()
    manifest = json.loads(
        (ROOT / "content" / "question-bank-manifest.json").read_text(encoding="utf-8")
    )
    display_names = {
        question["primary_track"]: question["primary_track"].replace("-", " ").title()
        for question in manifest["questions"]
    }
    with psycopg.connect(args.database_url) as connection, connection.cursor() as cursor:
        for slug, target_count in manifest["track_targets"].items():
            cursor.execute(
                """
                INSERT INTO question_tracks (slug, name, target_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name, target_count = EXCLUDED.target_count
                """,
                (slug, display_names[slug], target_count),
            )
        for source_name, domain, category in DISCOVERED_SOURCES:
            cursor.execute(
                """
                INSERT INTO source_registry (
                    source_name, canonical_domain, source_category,
                    discovery_method, access_method, rights_status,
                    coverage_level, collection_mode, connector_status
                ) VALUES (
                    %s, %s, %s, 'curated-launch-registry', 'manual_review',
                    'unreviewed', 'DISCOVERY_ONLY', 'manual', 'unreviewed'
                )
                ON CONFLICT (canonical_domain) DO UPDATE SET
                    source_name=EXCLUDED.source_name,
                    source_category=EXCLUDED.source_category,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (source_name, domain, category),
            )
        for slug, name in COMPETENCIES:
            cursor.execute(
                """
                INSERT INTO competencies (slug, name, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    description=EXCLUDED.description,
                    last_updated_at=CURRENT_TIMESTAMP
                """,
                (
                    slug,
                    name,
                    f"Platform-independent interview competency covering {name.casefold()}.",
                ),
            )
        connection.commit()
    print(
        f"seeded {len(manifest['track_targets'])} tracks, "
        f"{len(DISCOVERED_SOURCES)} discovered sources, and "
        f"{len(COMPETENCIES)} competencies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
