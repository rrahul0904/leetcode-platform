from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionRequestedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    event_type: Literal["execution.requested"]
    execution_id: UUID
    attempt: int = Field(ge=1)
    requested_at: datetime
    trace_id: str = Field(min_length=1, max_length=160)


class ExecutionCancelRequestedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    event_type: Literal["execution.cancel_requested"]
    execution_id: UUID
    requested_at: datetime
    trace_id: str = Field(min_length=1, max_length=160)


ExecutionQueueEvent = ExecutionRequestedEvent | ExecutionCancelRequestedEvent


def parse_execution_queue_event(payload: object) -> ExecutionQueueEvent:
    if not isinstance(payload, dict):
        raise ValueError("Execution queue event must be a JSON object.")
    event_type = payload.get("event_type")
    if event_type == "execution.requested":
        return ExecutionRequestedEvent.model_validate(payload)
    if event_type == "execution.cancel_requested":
        return ExecutionCancelRequestedEvent.model_validate(payload)
    raise ValueError("Unsupported execution queue event type.")
