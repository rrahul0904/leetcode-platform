#!/usr/bin/env python3
"""Deterministic exact and lexical duplicate checks for planning metadata."""

from __future__ import annotations

import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[a-z0-9]+")


def tokens(value: str) -> set[str]:
    return set(TOKEN.findall(value.casefold()))


def main() -> int:
    questions = json.loads(
        (ROOT / "content" / "question-bank-manifest.json").read_text(encoding="utf-8")
    )["questions"]
    exact_keys = [
        f"{question['working_title'].casefold()}|{question['learning_objective'].casefold()}"
        for question in questions
    ]
    exact = [value for value, count in Counter(exact_keys).items() if count > 1]
    if exact:
        print(f"duplicate check failed: {len(exact)} exact duplicate(s)")
        return 1

    review_pairs = 0
    for left, right in combinations(questions, 2):
        if left["primary_track"] != right["primary_track"]:
            continue
        left_tokens = tokens(left["working_title"])
        right_tokens = tokens(right["working_title"])
        score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if score >= 0.82:
            review_pairs += 1
    print(
        "duplicate check passed: 0 exact duplicates; "
        f"{review_pairs} lexical pair(s) require editorial distinctness review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
