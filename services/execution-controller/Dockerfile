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
LABEL org.opencontainers.image.title="Rigor Execution Controller" \
      org.opencontainers.image.description="Trusted SQS to gVisor execution controller" \
      org.opencontainers.image.version="0.1.0-local"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.13 \
        /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
        /usr/local/lib/python3.13/site-packages/setuptools \
        /usr/local/lib/python3.13/site-packages/setuptools-*.dist-info \
    && groupadd --gid 10001 rigor \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rigor

WORKDIR /app
COPY --from=builder --chown=rigor:rigor /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RIGOR_ENVIRONMENT=production

USER 10001:10001

CMD ["python", "-m", "rigor_api.execution_controller"]
