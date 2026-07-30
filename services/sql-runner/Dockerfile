# syntax=docker/dockerfile:1.8

ARG PYTHON_IMAGE=python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    HOME=/workspace \
    TMPDIR=/workspace/tmp

WORKDIR /opt/rigor
RUN pip install --no-cache-dir "psycopg[binary]==3.3.4"
COPY services/sql-runner/runner.py /opt/rigor/runner.py

RUN mkdir -p /workspace/tmp \
    && chown -R 65532:65532 /workspace \
    && chmod 0555 /opt/rigor/runner.py

USER 65532:65532

ENTRYPOINT ["python", "-I", "/opt/rigor/runner.py"]
