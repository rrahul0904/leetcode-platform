"""Provider boundary for tutor response generation.

The intervention gate and public-context projection happen before this boundary.
Providers therefore decide how to phrase an authorized coaching intervention, not
whether hidden evaluator state can be revealed. The deterministic Socratic coach is
always available as a fail-safe fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import get_settings
from .tutor_coach import TutorCoachContext, TutorCoachReply, deterministic_coach_reply


class TutorProvider(Protocol):
    """Minimal provider contract for text tutoring."""

    @property
    def name(self) -> str: ...

    def respond(self, context: TutorCoachContext) -> TutorCoachReply: ...


@dataclass(frozen=True)
class DeterministicTutorProvider:
    name: str = "skillforge"

    def respond(self, context: TutorCoachContext) -> TutorCoachReply:
        return deterministic_coach_reply(context)


@dataclass(frozen=True)
class UnavailableTutorProvider:
    """Represents a configured adapter that has no approved runtime binding yet."""

    name: str

    def respond(self, _context: TutorCoachContext) -> TutorCoachReply:
        raise RuntimeError(f"Tutor provider {self.name!r} is not available")


@dataclass(frozen=True)
class TutorProviderService:
    primary: TutorProvider
    fallback: TutorProvider

    def respond(self, context: TutorCoachContext) -> TutorCoachReply:
        try:
            return self.primary.respond(context)
        except Exception:
            if self.primary is self.fallback:
                raise
            fallback_reply = self.fallback.respond(context)
            return TutorCoachReply(
                text=fallback_reply.text,
                provider=f"{fallback_reply.provider}-fallback",
                model=fallback_reply.model,
            )


def build_tutor_provider_service(adapter: str | None = None) -> TutorProviderService:
    """Build the configured provider service without accepting arbitrary endpoints.

    Only explicitly implemented adapters may become a network-backed primary.
    Unknown or not-yet-bound adapters degrade to the deterministic tutor instead of
    turning configuration into an SSRF-capable arbitrary HTTP provider.
    """

    configured = (adapter or get_settings().ai_adapter).strip().upper()
    deterministic = DeterministicTutorProvider()
    if configured in {"", "DETERMINISTIC", "SKILLFORGE"}:
        return TutorProviderService(primary=deterministic, fallback=deterministic)
    return TutorProviderService(
        primary=UnavailableTutorProvider(name=configured.casefold()),
        fallback=deterministic,
    )
