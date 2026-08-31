from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import Connection, Engine, create_engine, text

from .config import Settings
from .schemas import AuthenticatedPrincipal


def normalize_database_url(value: str) -> str:
    """Use the installed psycopg v3 driver for standard managed-Postgres URLs."""
    if value.startswith("postgres://"):
        return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
    if value.startswith("postgresql://"):
        return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
    return value


def create_database_engine(settings: Settings, database_url: str | None = None) -> Engine:
    return create_engine(
        normalize_database_url(database_url or settings.database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


def database_engine(request: Request) -> Engine:
    value: Engine = request.app.state.database_engine
    return value


DatabaseEngine = Annotated[Engine, Depends(database_engine)]


def operational_database_engine(request: Request) -> Engine:
    value: Engine = request.app.state.operational_database_engine
    return value


OperationalDatabaseEngine = Annotated[Engine, Depends(operational_database_engine)]


def set_principal_context(
    connection: Connection,
    principal: AuthenticatedPrincipal,
    principal_user_id: UUID,
) -> None:
    """Set transaction-local identity used by PostgreSQL RLS policies."""
    connection.execute(
        text("SELECT set_config('rigor.user_id', :user_id, true)"),
        {"user_id": str(principal_user_id)},
    )
    connection.execute(
        text("SELECT set_config('rigor.organization_id', :organization_id, true)"),
        {"organization_id": principal.organization_id or ""},
    )
    connection.execute(text("SELECT set_config('rigor.maintenance_bypass', 'off', true)"))


@contextmanager
def principal_transaction(
    engine: Engine,
    principal: AuthenticatedPrincipal,
) -> Generator[Connection]:
    """Open a transaction whose RLS identity cannot leak through the pool.

    ``ensure_user`` refreshes identity metadata and, only for the controlled local
    OIDC development provider, bootstraps deterministic test roles. External
    identity never mutates PostgreSQL authorization state through this path.
    """

    with engine.begin() as connection:
        # Local import keeps the low-level database module independent while
        # guaranteeing the persisted user id and RLS context share a transaction.
        from .persistence import ensure_user

        principal_user_id = ensure_user(connection, principal)
        set_principal_context(connection, principal, principal_user_id)
        yield connection


@contextmanager
def maintenance_transaction(engine: Engine) -> Generator[Connection]:
    """Open the explicit migrator-only RLS maintenance path.

    PostgreSQL policies additionally verify ``session_user = 'rigor_migrator'``;
    setting the custom GUC from the runtime role does not grant a bypass.
    """
    with engine.begin() as connection:
        connection.execute(text("SELECT set_config('rigor.maintenance_bypass', 'on', true)"))
        yield connection
