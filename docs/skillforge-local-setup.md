# SkillForge local setup

The repository already has a hardened local Docker topology. Preserve that topology rather than creating a second incompatible scaffold.

```bash
cp .env.example .env
docker compose up --build
```

Current host ports are intentionally offset to avoid collisions:

- Web: http://localhost:3001
- FastAPI / local OIDC: http://localhost:8002
- PostgreSQL: localhost:5434
- Valkey: localhost:6381

Inside Docker, PostgreSQL remains on 5432 and Valkey on 6379. The execution controller and Python/SQL runners are private container-network services.

Database migrations:

```bash
uv run alembic upgrade head
```

Frontend development:

```bash
pnpm install --frozen-lockfile
pnpm --filter @rigor/web dev
```

Backend development:

```bash
uv sync --frozen --all-packages
uv run uvicorn rigor_api.main:app --host 0.0.0.0 --port 8002 --reload
```

Local authentication uses the controlled local OIDC/PKCE provider. Production disables it and validates Clerk JWTs via issuer/JWKS settings.
