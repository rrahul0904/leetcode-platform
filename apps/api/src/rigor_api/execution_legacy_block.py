from __future__ import annotations

from fastapi import HTTPException, status

from .practice import router


@router.post("/questions/{slug}/run", include_in_schema=False)
def legacy_synchronous_run_disabled(slug: str) -> None:
    del slug
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Synchronous candidate execution is disabled. Use /api/v1/executions/run.",
    )


@router.post("/questions/{slug}/submissions", include_in_schema=False)
def legacy_synchronous_submit_disabled(slug: str) -> None:
    del slug
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Synchronous candidate execution is disabled. Use /api/v1/executions/submit.",
    )


LEGACY_SYNCHRONOUS_EXECUTION_BLOCKED = True
