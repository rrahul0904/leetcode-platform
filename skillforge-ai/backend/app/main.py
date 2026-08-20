from __future__ import annotations

import ast
import csv
import importlib
import io
import json
import os
import sqlite3
import time
from contextlib import redirect_stdout
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = FastAPI(title="SkillForge AI API", version="0.3.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class PythonRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50_000)
    stdin: str = Field(default="", max_length=10_000)


class SqlRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=50_000)


class ImportValidateRequest(BaseModel):
    format: str
    records: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)


class ExportRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list, max_length=10_000)
    filename: str = Field(default="skillforge-export", max_length=120)
    title: str = Field(default="SkillForge AI Export", max_length=200)


class BatchGenerateRequest(BaseModel):
    prompts: list[str] = Field(min_length=1, max_length=50)
    system_prompt: str = Field(
        default="You are SkillForge AI, a rigorous data-engineering interview tutor.",
        max_length=5000,
    )
    model: str | None = None


class BatchEmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=100)
    model: str | None = None


class RunResponse(BaseModel):
    status: str
    output: str
    runtime_ms: int


SAFE_MODULES = {"collections", "math", "heapq", "bisect", "itertools", "functools"}
BLOCKED_PYTHON_NODES = (ast.With, ast.AsyncWith, ast.Global, ast.Nonlocal)


def validate_demo_python(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Syntax error: {exc.msg}") from exc
    for node in ast.walk(tree):
        if isinstance(node, BLOCKED_PYTHON_NODES):
            raise HTTPException(
                status_code=400,
                detail=f"{type(node).__name__} is disabled in demo execution",
            )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [alias.name.split(".")[0] for alias in node.names]
                if isinstance(node, ast.Import)
                else [(node.module or "").split(".")[0]]
            )
            if any(module not in SAFE_MODULES for module in modules):
                raise HTTPException(
                    status_code=400,
                    detail="Only a small standard-library allowlist is enabled in demo execution",
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "compile", "open", "input"}
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{node.func.id}() is disabled in demo execution",
            )


def safe_import(
    name: str,
    globals: dict[str, Any] | None = None,
    locals: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> Any:
    root = name.split(".")[0]
    if root not in SAFE_MODULES:
        raise ImportError(f"module {root!r} is not allowed")
    return importlib.import_module(name)


def seeded_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "create table facts (fact_id integer, carrier_id integer, site_id integer, category_id integer, event_ts text, ingest_seq integer, region text, status text, duration real, latency real)"
    )
    conn.executemany(
        "insert into facts values (?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 101, 10, 1, "2026-01-01 09:00", 1, "NA", "completed", 120, 120),
            (2, 101, 10, 2, "2026-01-02 10:00", 2, "APAC", "active", 80, 108),
            (3, 202, 20, 1, "2026-01-03 11:00", 3, "APAC", "completed", 150, 150),
            (4, 202, 20, 3, "2026-01-04 12:00", 4, "EMEA", "completed", 95, 90),
        ],
    )
    conn.execute(
        "create table dim_category (category_id integer primary key, category_name text)"
    )
    conn.executemany(
        "insert into dim_category values (?,?)",
        [(1, "Core"), (2, "Premium"), (3, "Legacy")],
    )
    return conn


def provider_config() -> tuple[str, str, str, str]:
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI provider is not configured. Set AI_API_KEY or OPENAI_API_KEY.",
        )
    base_url = (os.getenv("AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    chat_model = os.getenv("AI_CHAT_MODEL") or "gpt-4.1-mini"
    embedding_model = os.getenv("AI_EMBEDDING_MODEL") or "text-embedding-3-small"
    return api_key, base_url, chat_model, embedding_model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "skillforge-api", "version": app.version}


@app.post("/runner/python", response_model=RunResponse)
def run_python(payload: PythonRunRequest) -> RunResponse:
    validate_demo_python(payload.code)
    started = time.perf_counter()
    stdout = io.StringIO()
    safe_builtins: dict[str, Any] = {
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "sum": sum,
        "min": min,
        "max": max,
        "sorted": sorted,
        "set": set,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "abs": abs,
        "all": all,
        "any": any,
        "print": print,
        "__import__": safe_import,
    }
    namespace: dict[str, Any] = {"__builtins__": safe_builtins}
    try:
        with redirect_stdout(stdout):
            exec(compile(payload.code, "<skillforge-demo>", "exec"), namespace, namespace)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Execution error: {type(exc).__name__}: {exc}",
        ) from exc
    runtime_ms = max(1, int((time.perf_counter() - started) * 1000))
    return RunResponse(
        status="completed",
        output=stdout.getvalue() or "Program completed with no stdout.",
        runtime_ms=runtime_ms,
    )


@app.post("/runner/sql", response_model=RunResponse)
def run_sql(payload: SqlRunRequest) -> RunResponse:
    normalized = " ".join(payload.query.lower().split())
    if not normalized.startswith(("select", "with")):
        raise HTTPException(
            status_code=400,
            detail="Demo SQL runner is read-only; only SELECT/CTE statements are accepted",
        )
    if any(
        token in f" {normalized} "
        for token in [
            " drop ",
            " delete ",
            " update ",
            " insert ",
            " alter ",
            " truncate ",
            " attach ",
            " pragma ",
        ]
    ):
        raise HTTPException(
            status_code=400, detail="Mutating or administrative SQL is disabled"
        )
    started = time.perf_counter()
    conn = seeded_sqlite()
    try:
        cur = conn.execute(payload.query)
        columns = [item[0] for item in cur.description or []]
        rows = cur.fetchmany(100)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f"SQL error: {exc}") from exc
    finally:
        conn.close()
    runtime_ms = max(1, int((time.perf_counter() - started) * 1000))
    table = "\t".join(columns) + "\n" + "\n".join(
        "\t".join(str(value) for value in row) for row in rows
    )
    return RunResponse(status="completed", output=table, runtime_ms=runtime_ms)


@app.post("/imports/validate")
def validate_import(payload: ImportValidateRequest) -> dict[str, Any]:
    required = {"public_id", "title", "difficulty", "question_type", "body"}
    invalid: list[dict[str, Any]] = []
    for index, record in enumerate(payload.records):
        missing = sorted(required - record.keys())
        if missing:
            invalid.append({"index": index, "missing": missing})
    return {
        "format": payload.format,
        "total": len(payload.records),
        "valid": len(payload.records) - len(invalid),
        "invalid": len(invalid),
        "errors": invalid[:100],
    }


@app.post("/imports/process")
def process_import(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "queued",
        "job_type": "content_import",
        "payload_keys": sorted(payload.keys()),
        "note": "Wire this contract to the Redis worker for production-scale imports.",
    }


@app.post("/exports/json")
def export_json(payload: ExportRequest) -> Response:
    body = json.dumps(payload.records, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={"content-disposition": f'attachment; filename="{payload.filename}.json"'},
    )


@app.post("/exports/csv")
def export_csv(payload: ExportRequest) -> Response:
    columns = sorted({key for record in payload.records for key in record.keys()})
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in payload.records:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for key, value in record.items()
            }
        )
    return Response(
        content=stream.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"content-disposition": f'attachment; filename="{payload.filename}.csv"'},
    )


@app.post("/exports/pdf")
def export_pdf(payload: ExportRequest) -> Response:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 54
    pdf.setTitle(payload.title)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(54, y, payload.title)
    y -= 26
    pdf.setFont("Helvetica", 8)

    for index, record in enumerate(payload.records, start=1):
        lines = [f"{index}. {record.get('public_id', '')} {record.get('title', '')}".strip()]
        for key in ("difficulty", "question_type", "body", "explanation"):
            if record.get(key) not in (None, ""):
                lines.append(f"{key}: {record[key]}")
        for raw_line in lines:
            chunks = [raw_line[i : i + 110] for i in range(0, len(raw_line), 110)] or [""]
            for line in chunks:
                if y < 54:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 8)
                    y = height - 54
                pdf.drawString(54, y, line)
                y -= 11
        y -= 6

    pdf.save()
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"content-disposition": f'attachment; filename="{payload.filename}.pdf"'},
    )


@app.post("/ai/batch-generate")
def batch_generate(payload: BatchGenerateRequest) -> dict[str, Any]:
    api_key, base_url, default_model, _ = provider_config()
    model = payload.model or default_model
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        for index, prompt in enumerate(payload.prompts):
            response = client.post(
                f"{base_url}/chat/completions",
                headers={"authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": payload.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            if response.is_error:
                results.append(
                    {
                        "index": index,
                        "status": "error",
                        "http_status": response.status_code,
                    }
                )
                continue
            body = response.json()
            results.append(
                {
                    "index": index,
                    "status": "completed",
                    "content": body.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", ""),
                    "usage": body.get("usage"),
                }
            )
    return {
        "status": "completed",
        "model": model,
        "count": len(results),
        "results": results,
    }


@app.post("/ai/batch-embed")
def batch_embed(payload: BatchEmbedRequest) -> dict[str, Any]:
    api_key, base_url, _, default_model = provider_config()
    model = payload.model or default_model
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{base_url}/embeddings",
            headers={"authorization": f"Bearer {api_key}"},
            json={"model": model, "input": payload.texts},
        )
    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding provider returned {response.status_code}",
        )
    body = response.json()
    embeddings = [item.get("embedding", []) for item in body.get("data", [])]
    return {
        "status": "completed",
        "model": model,
        "count": len(embeddings),
        "embeddings": embeddings,
        "usage": body.get("usage"),
    }
