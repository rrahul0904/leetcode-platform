from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine

from .config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


def database_engine(request: Request) -> Engine:
    value: Engine = request.app.state.database_engine
    return value


DatabaseEngine = Annotated[Engine, Depends(database_engine)]
