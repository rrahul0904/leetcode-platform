from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> int:
    database_url = os.getenv("RIGOR_EXECUTOR_DATABASE_URL", "")
    if not database_url:
        return 1
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            healthy = connection.execute(
                text(
                    """
                    SELECT heartbeat_at > CURRENT_TIMESTAMP - INTERVAL '30 seconds'
                    FROM local_execution_controller_status
                    WHERE controller_key='local'
                    """
                )
            ).scalar_one_or_none()
        return 0 if healthy is True else 1
    except Exception:
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
