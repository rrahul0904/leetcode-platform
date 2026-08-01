-- Local PostgreSQL role topology. Production supplies equivalent login
-- credentials through infrastructure-managed secrets and must not reuse these
-- local-only passwords. Execution roles deliberately do not use BYPASSRLS.
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_owner') THEN
        CREATE ROLE rigor_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_migrator') THEN
        CREATE ROLE rigor_migrator LOGIN PASSWORD 'rigor_migrator_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_app') THEN
        CREATE ROLE rigor_app LOGIN PASSWORD 'rigor_app_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_readonly') THEN
        CREATE ROLE rigor_readonly LOGIN PASSWORD 'rigor_readonly_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_execution_worker') THEN
        CREATE ROLE rigor_execution_worker LOGIN PASSWORD 'rigor_execution_worker_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_execution_reconciler') THEN
        CREATE ROLE rigor_execution_reconciler LOGIN PASSWORD 'rigor_execution_reconciler_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    -- Compatibility login used by existing local controller configuration. It
    -- inherits only the execution-worker role instead of bypassing RLS.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_executor') THEN
        CREATE ROLE rigor_executor LOGIN PASSWORD 'rigor_executor_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rigor_sql_sandbox') THEN
        CREATE ROLE rigor_sql_sandbox LOGIN PASSWORD 'rigor_sql_sandbox_local_only'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END
$roles$;

ALTER ROLE rigor_migrator NOBYPASSRLS;
ALTER ROLE rigor_app NOBYPASSRLS;
ALTER ROLE rigor_readonly BYPASSRLS;
ALTER ROLE rigor_execution_worker NOBYPASSRLS;
ALTER ROLE rigor_execution_reconciler NOBYPASSRLS;
ALTER ROLE rigor_executor NOBYPASSRLS;
ALTER ROLE rigor_sql_sandbox NOBYPASSRLS;

GRANT rigor_execution_worker TO rigor_executor;

ALTER DATABASE rigor OWNER TO rigor_owner;
ALTER SCHEMA public OWNER TO rigor_owner;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

REVOKE ALL ON DATABASE rigor FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE rigor TO rigor_migrator, rigor_app, rigor_readonly;
GRANT CONNECT ON DATABASE rigor TO rigor_execution_worker, rigor_execution_reconciler;
GRANT CONNECT ON DATABASE rigor TO rigor_executor, rigor_sql_sandbox;
GRANT USAGE, CREATE ON SCHEMA public TO rigor_migrator;
GRANT USAGE ON SCHEMA public TO rigor_app, rigor_readonly;
GRANT USAGE ON SCHEMA public TO rigor_execution_worker, rigor_execution_reconciler;
GRANT USAGE ON SCHEMA public TO rigor_executor;

-- The SQL sandbox role may connect to the local cluster for trusted reference
-- validation, but receives no application schema or table privileges. Production
-- candidate SQL uses an execution-local PostgreSQL instance instead.
REVOKE ALL ON SCHEMA public FROM rigor_sql_sandbox;

ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rigor_app;
ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO rigor_app;
ALTER DEFAULT PRIVILEGES FOR ROLE rigor_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO rigor_readonly;
