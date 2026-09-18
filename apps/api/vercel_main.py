"""Vercel service entrypoint for the existing Rigor/SkillForge FastAPI app.

This module intentionally contains no business logic. Vercel imports the same
application composition used by the normal API process so authorization,
catalog, drafts, submissions, evidence, and readiness stay single-sourced.
"""

from rigor_api.main import app

__all__ = ["app"]
