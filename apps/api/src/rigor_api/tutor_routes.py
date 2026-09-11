from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from .auth import require_permissions
from .schemas import AuthenticatedPrincipal
from .tutor_domain import TutorContextSnapshot, TutorIntervention, decide_intervention

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])


class TutorRouteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TutorCapabilities(TutorRouteModel):
    text_sessions: bool
    code_context: bool
    whiteboard_context: bool
    adaptive_interventions: bool
    realtime_voice: bool
    persistent_sessions: bool
    mastery_updates: bool
    hidden_evaluation_exposed: bool


TutorReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("profile:read")),
]


@router.get("/capabilities", response_model=TutorCapabilities)
def get_tutor_capabilities(_principal: TutorReadPrincipal) -> TutorCapabilities:
    """Return server-authoritative rollout state for candidate tutor features."""

    return TutorCapabilities(
        text_sessions=False,
        code_context=True,
        whiteboard_context=True,
        adaptive_interventions=True,
        realtime_voice=False,
        persistent_sessions=False,
        mastery_updates=False,
        hidden_evaluation_exposed=False,
    )


@router.post("/interventions/decide", response_model=TutorIntervention)
def decide_tutor_intervention(
    payload: TutorContextSnapshot,
    _principal: TutorReadPrincipal,
) -> TutorIntervention:
    """Apply the deterministic intervention gate before any model is allowed to speak."""

    return decide_intervention(payload)
