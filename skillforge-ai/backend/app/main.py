from __future__ import annotations

import ast
import importlib
import io
import os
import sqlite3
import time
from contextlib import redirect_stdout
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="SkillForge AI API", version="0.2.0")
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

class PythonRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50_000)
    stdin: str = Field(default="", max_length=10_000)

class SqlRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=50_000)

class ImportValidateRequest(BaseModel):
    format: str
    records: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)

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
            raise HTTPException(status_code=400, detail=f"{type(node).__name__} is disabled in demo execution")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(module not in SAFE_MODULES for module in modules):
                raise HTTPException(status_code=400, detail="Only a small standard-library allowlist is enabled in demo execution")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "open", "input"}:
            raise HTTPException(status_code=400, detail=f"{node.func.id}() is disabled in demo execution")

def safe_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    root = name.split(".")[0]
    if root not in SAFE_MODULES:
        raise ImportError(f"module {root!r} is not allowed")
    return importlib.import_module(name)

def seeded_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table facts (fact_id integer, carrier_id integer, site_id integer, category_id integer, event_ts text, ingest_seq integer, region text, status text, duration real, latency real)")
    conn.executemany("insert into facts values (?,?,?,?,?,?,?,?,?,?)", [(1,101,10,1,"2026-01-01 09:00",1,"NA","completed",120,120),(2,101,10,2,"2026-01-02 10:00",2,"APAC","active",80,108),(3,202,20,1,"2026-01-03 11:00",3,"APAC","completed",150,150),(4,202,20,3,"2026-01-04 12:00",4,"EMEA","completed",95,90)])
    conn.execute("create table dim_category (category_id integer primary key, category_name text)")
    conn.executemany("insert into dim_category values (?,?)", [(1,"Core"),(2,"Premium"),(3,"Legacy")])
    return conn

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "skillforge-api", "version": app.version}

@app.post("/runner/python", response_model=RunResponse)
def run_python(payload: PythonRunRequest) -> RunResponse:
    validate_demo_python(payload.code)
    started = time.perf_counter(); stdout = io.StringIO()
    safe_builtins: dict[str, Any] = {"len":len,"range":range,"enumerate":enumerate,"zip":zip,"sum":sum,"min":min,"max":max,"sorted":sorted,"set":set,"list":list,"dict":dict,"tuple":tuple,"str":str,"int":int,"float":float,"bool":bool,"abs":abs,"all":all,"any":any,"print":print,"__import__":safe_import}
    namespace: dict[str, Any] = {"__builtins__": safe_builtins}
    try:
        with redirect_stdout(stdout):
            exec(compile(payload.code, "<skillforge-demo>", "exec"), namespace, namespace)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Execution error: {type(exc).__name__}: {exc}") from exc
    runtime_ms = max(1, int((time.perf_counter() - started) * 1000))
    return RunResponse(status="completed", output=stdout.getvalue() or "Program completed with no stdout.", runtime_ms=runtime_ms)

@app.post("/runner/sql", response_model=RunResponse)
def run_sql(payload: SqlRunRequest) -> RunResponse:
    normalized = " ".join(payload.query.lower().split())
    if not normalized.startswith(("select", "with")):
        raise HTTPException(status_code=400, detail="Demo SQL runner is read-only; only SELECT/CTE statements are accepted")
    if any(token in f" {normalized} " for token in [" drop "," delete "," update "," insert "," alter "," truncate "," attach "," pragma "]):
        raise HTTPException(status_code=400, detail="Mutating or administrative SQL is disabled")
    started = time.perf_counter(); conn = seeded_sqlite()
    try:
        cur = conn.execute(payload.query); columns = [item[0] for item in cur.description or []]; rows = cur.fetchmany(100)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f"SQL error: {exc}") from exc
    finally:
        conn.close()
    runtime_ms = max(1, int((time.perf_counter() - started) * 1000))
    table = "\t".join(columns) + "\n" + "\n".join("\t".join(str(value) for value in row) for row in rows)
    return RunResponse(status="completed", output=table, runtime_ms=runtime_ms)

@app.post("/imports/validate")
def validate_import(payload: ImportValidateRequest) -> dict[str, Any]:
    required = {"public_id","title","difficulty","question_type","body"}; invalid: list[dict[str, Any]] = []
    for index, record in enumerate(payload.records):
        missing = sorted(required - record.keys())
        if missing: invalid.append({"index":index,"missing":missing})
    return {"format":payload.format,"total":len(payload.records),"valid":len(payload.records)-len(invalid),"invalid":len(invalid),"errors":invalid[:100]}

@app.post("/imports/process")
def process_import(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status":"queued","job_type":"content_import","payload_keys":sorted(payload.keys())}
