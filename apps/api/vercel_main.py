"""Vercel service entrypoint for the existing Rigor/SkillForge FastAPI app.

This module intentionally contains no business logic. Vercel imports the same
application composition used by the normal API process so authorization,
catalog, drafts, submissions, evidence, and readiness stay single-sourced.
"""

from pathlib import Path
import sys

# Vercel executes this entrypoint from the service root without installing the
# local src-layout package as an editable dependency. Put the service's src/
# directory on sys.path so the exact same rigor_api package used by tests and
# local processes can be imported in the hosted Python runtime.
source_root = Path(__file__).resolve().parent / "src"
source_root_text = str(source_root)
if source_root_text not in sys.path:
    sys.path.insert(0, source_root_text)

from rigor_api.main import app

__all__ = ["app"]
