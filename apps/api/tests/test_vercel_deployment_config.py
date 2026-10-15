from __future__ import annotations

import json
from pathlib import Path


def test_vercel_api_function_bundles_its_startup_manifest() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    configuration = json.loads((repository_root / "vercel.json").read_text(encoding="utf-8"))
    api_service = configuration["services"]["api"]
    function = api_service["functions"]["vercel_main.py"]

    included_manifest = (repository_root / "apps/api" / function["includeFiles"]).resolve()
    assert included_manifest == repository_root / "content/question-bank-manifest.json"
    assert included_manifest.is_file()
    assert "python -m pip install -r requirements.txt" in api_service["installCommand"]
