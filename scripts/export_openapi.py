#!/usr/bin/env python3
"""Export the canonical FastAPI OpenAPI document for client generation."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema
from rigor_api.main import app
from rigor_api.schemas import SHARED_API_CONTRACTS

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages" / "api-client" / "openapi.json"


def main() -> None:
    document = app.openapi()
    _, shared_schema = models_json_schema(
        [(model, "validation") for model in SHARED_API_CONTRACTS],
        ref_template="#/components/schemas/{model}",
    )
    components = document.setdefault("components", {}).setdefault("schemas", {})
    components.update(shared_schema.get("$defs", {}))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote OpenAPI {app.version} to {OUTPUT}")


if __name__ == "__main__":
    main()
