#!/usr/bin/env python3
"""Export the canonical FastAPI OpenAPI document for client generation."""

from __future__ import annotations

import json
from pathlib import Path

from rigor_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages" / "api-client" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote OpenAPI {app.version} to {OUTPUT}")


if __name__ == "__main__":
    main()
