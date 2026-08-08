# syntax=docker/dockerfile:1.8

ARG PYTHON_IMAGE=python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/question-schema/pyproject.toml packages/question-schema/pyproject.toml
COPY apps/api/src apps/api/src
COPY packages/question-schema/src packages/question-schema/src

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=build_ca,required=true \
    SSL_CERT_FILE=/run/secrets/build_ca \
    uv sync --frozen --no-dev --package rigor-api --no-editable

FROM ${PYTHON_IMAGE} AS runtime
LABEL org.opencontainers.image.title="Rigor API" \
      org.opencontainers.image.description="Rigor modular-monolith API and database maintenance image" \
      org.opencontainers.image.version="0.1.0-local"

RUN groupadd --gid 10001 rigor \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rigor

WORKDIR /app
COPY --from=builder --chown=rigor:rigor /app/.venv /app/.venv
COPY --chown=rigor:rigor content content
COPY --chown=rigor:rigor alembic.ini alembic.ini
COPY --chown=rigor:rigor database/migrations database/migrations
COPY --chown=rigor:rigor scripts/seed_database.py scripts/seed_database.py
COPY --chown=rigor:rigor scripts/collect_external_references.py scripts/collect_external_references.py
COPY --chown=rigor:rigor scripts/sync_content.py scripts/sync_content.py
COPY --chown=rigor:rigor scripts/publish_local_catalog.py scripts/publish_local_catalog.py
COPY --chown=rigor:rigor scripts/import_source_backed_question_bank.py scripts/import_source_backed_question_bank.py
COPY --chown=rigor:rigor scripts/verify_source_bank_release.py scripts/verify_source_bank_release.py

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RIGOR_CONTENT_ROOT=/app/content \
    RIGOR_ENVIRONMENT=production

USER 10001:10001
EXPOSE 8002
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8002/readyz', timeout=2)); assert data['status']=='ready'"]

CMD ["uvicorn", "rigor_api.main:app", "--host", "0.0.0.0", "--port", "8002"]
