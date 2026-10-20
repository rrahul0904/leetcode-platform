from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vercel_api_service_pins_supported_python_minor() -> None:
    project_config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    api_root = project_config["services"]["api"]["root"].strip("/")
    assert api_root == "apps/api"

    root_python = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    service_python = (ROOT / api_root / ".python-version").read_text(
        encoding="utf-8"
    ).strip()
    assert root_python == service_python == "3.13"

    with (ROOT / api_root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    assert pyproject["project"]["requires-python"] == ">=3.13,<3.14"
