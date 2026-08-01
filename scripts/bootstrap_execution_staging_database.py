from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from typing import cast
from urllib.parse import quote_plus

import psycopg
from psycopg import sql


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    port: int
    database: str


@dataclass(frozen=True)
class LoginCredential:
    username: str
    password: str

    def sqlalchemy_url(self, target: DatabaseTarget) -> str:
        return (
            "postgresql+psycopg://"
            f"{quote_plus(self.username)}:{quote_plus(self.password)}"
            f"@{target.host}:{target.port}/{target.database}"
            "?sslmode=require"
        )


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BootstrapError(f"{name} is required.")
    return value


def aws_cli(*args: str) -> str:
    command = ["aws", *args]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise BootstrapError(
            f"AWS CLI command failed ({' '.join(command[:3])} ...): "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def master_credential(secret_arn: str, region: str) -> LoginCredential:
    raw = aws_cli(
        "secretsmanager",
        "get-secret-value",
        "--region",
        region,
        "--secret-id",
        secret_arn,
        "--query",
        "SecretString",
        "--output",
        "text",
    )
    value: object = json.loads(raw)
    if not isinstance(value, dict):
        raise BootstrapError("RDS master secret is not a JSON object.")
    payload = cast(dict[str, object], value)
    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not username:
        raise BootstrapError("RDS master secret has no username.")
    if not isinstance(password, str) or not password:
        raise BootstrapError("RDS master secret has no password.")
    return LoginCredential(username=username, password=password)


def generated_login(username: str) -> LoginCredential:
    return LoginCredential(username=username, password=secrets.token_urlsafe(36))


def role_exists(connection: psycopg.Connection[object], role: str) -> bool:
    return (
        connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
        is not None
    )


def ensure_group_role(connection: psycopg.Connection[object], role: str) -> None:
    identifier = sql.Identifier(role)
    if role_exists(connection, role):
        connection.execute(
            sql.SQL(
                "ALTER ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS"
            ).format(identifier)
        )
        return
    connection.execute(
        sql.SQL(
            "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS"
        ).format(identifier)
    )


def ensure_login_role(
    connection: psycopg.Connection[object],
    credential: LoginCredential,
    *,
    readonly: bool = False,
) -> None:
    identifier = sql.Identifier(credential.username)
    password = sql.Literal(credential.password)
    inherit = sql.SQL("NOINHERIT") if readonly else sql.SQL("INHERIT")
    attributes = sql.SQL(
        "LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE {} "
        "NOREPLICATION NOBYPASSRLS"
    ).format(password, inherit)
    if role_exists(connection, credential.username):
        connection.execute(sql.SQL("ALTER ROLE {} ").format(identifier) + attributes)
        return
    connection.execute(sql.SQL("CREATE ROLE {} ").format(identifier) + attributes)


def bootstrap_roles(
    target: DatabaseTarget,
    master: LoginCredential,
    migrator: LoginCredential,
    application: LoginCredential,
    executor: LoginCredential,
    readonly: LoginCredential,
) -> None:
    with psycopg.connect(
        host=target.host,
        port=target.port,
        dbname=target.database,
        user=master.username,
        password=master.password,
        sslmode="require",
        autocommit=True,
    ) as connection:
        ensure_group_role(connection, "rigor_owner")
        ensure_group_role(connection, "rigor_execution_worker")
        ensure_group_role(connection, "rigor_execution_reconciler")
        ensure_login_role(connection, migrator)
        ensure_login_role(connection, application)
        ensure_login_role(connection, executor)
        ensure_login_role(connection, readonly, readonly=True)

        connection.execute("GRANT rigor_execution_worker TO rigor_executor")
        connection.execute(sql.SQL("ALTER DATABASE {} OWNER TO rigor_owner").format(
            sql.Identifier(target.database)
        ))
        connection.execute("ALTER SCHEMA public OWNER TO rigor_owner")

        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

        connection.execute("REVOKE ALL ON DATABASE rigor FROM PUBLIC")
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute(
            "GRANT CONNECT ON DATABASE rigor TO rigor_migrator, rigor_app, rigor_readonly"
        )
        connection.execute(
            "GRANT CONNECT ON DATABASE rigor TO rigor_execution_worker, "
            "rigor_execution_reconciler, rigor_executor"
        )
        connection.execute("GRANT USAGE, CREATE ON SCHEMA public TO rigor_migrator")
        connection.execute("GRANT USAGE ON SCHEMA public TO rigor_app, rigor_readonly")
        connection.execute(
            "GRANT USAGE ON SCHEMA public TO rigor_execution_worker, "
            "rigor_execution_reconciler, rigor_executor"
        )

        connection.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rigor_app"
        )
        connection.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO rigor_app"
        )
        connection.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public "
            "GRANT SELECT ON TABLES TO rigor_readonly"
        )


def secret_payload(target: DatabaseTarget, credential: LoginCredential) -> str:
    return json.dumps(
        {
            "host": target.host,
            "port": target.port,
            "dbname": target.database,
            "username": credential.username,
            "password": credential.password,
            "database_url": credential.sqlalchemy_url(target),
        },
        separators=(",", ":"),
    )


def put_secret(region: str, name: str, payload: str) -> None:
    exists = subprocess.run(
        [
            "aws",
            "secretsmanager",
            "describe-secret",
            "--region",
            region,
            "--secret-id",
            name,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    ).returncode == 0
    if exists:
        aws_cli(
            "secretsmanager",
            "put-secret-value",
            "--region",
            region,
            "--secret-id",
            name,
            "--secret-string",
            payload,
        )
        return
    aws_cli(
        "secretsmanager",
        "create-secret",
        "--region",
        region,
        "--name",
        name,
        "--secret-string",
        payload,
        "--description",
        "Rigor staging database credential managed by trusted bootstrap tooling",
    )


def run_migrations(migrator: LoginCredential, target: DatabaseTarget) -> None:
    environment = os.environ.copy()
    environment["RIGOR_DATABASE_URL"] = migrator.sqlalchemy_url(target)
    completed = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=False,
        env=environment,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise BootstrapError("Alembic upgrade head failed under rigor_migrator.")


def verify_security(target: DatabaseTarget, master: LoginCredential) -> None:
    with psycopg.connect(
        host=target.host,
        port=target.port,
        dbname=target.database,
        user=master.username,
        password=master.password,
        sslmode="require",
    ) as connection:
        rows = connection.execute(
            """
            SELECT rolname, rolbypassrls, rolsuper, rolcreatedb, rolcreaterole
            FROM pg_roles
            WHERE rolname IN (
              'rigor_app', 'rigor_migrator', 'rigor_execution_worker',
              'rigor_execution_reconciler', 'rigor_executor'
            )
            ORDER BY rolname
            """
        ).fetchall()
    if len(rows) != 5:
        raise BootstrapError("One or more required staging database roles are missing.")
    for row in rows:
        role, bypass, superuser, createdb, createrole = row
        if bypass or superuser or createdb or createrole:
            raise BootstrapError(f"Unsafe database privilege detected for {role}.")


def main() -> int:
    try:
        region = required_env("AWS_REGION")
        target = DatabaseTarget(
            host=required_env("RIGOR_STAGING_DATABASE_HOST"),
            port=int(os.getenv("RIGOR_STAGING_DATABASE_PORT", "5432")),
            database=os.getenv("RIGOR_STAGING_DATABASE_NAME", "rigor"),
        )
        secret_prefix = os.getenv(
            "RIGOR_STAGING_DATABASE_SECRET_PREFIX",
            "rigor-staging/database",
        ).rstrip("/")
        master = master_credential(
            required_env("RIGOR_STAGING_DATABASE_MASTER_SECRET_ARN"),
            region,
        )

        migrator = generated_login("rigor_migrator")
        application = generated_login("rigor_app")
        executor = generated_login("rigor_executor")
        readonly = generated_login("rigor_readonly")

        bootstrap_roles(target, master, migrator, application, executor, readonly)
        run_migrations(migrator, target)
        verify_security(target, master)

        credentials = {
            "migrator": migrator,
            "app": application,
            "executor": executor,
            "readonly": readonly,
        }
        for name, credential in credentials.items():
            put_secret(
                region,
                f"{secret_prefix}/{name}",
                secret_payload(target, credential),
            )

        print(
            "STAGING DATABASE BOOTSTRAPPED: roles, migrations, RLS prerequisites, "
            "and Secrets Manager credentials are ready."
        )
        return 0
    except (BootstrapError, ValueError, json.JSONDecodeError, psycopg.Error) as exc:
        print(f"STAGING DATABASE BOOTSTRAP FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
