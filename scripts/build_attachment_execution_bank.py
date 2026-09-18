#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, copy, hashlib, json, re, sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

ARROW_RE = re.compile(r"\s(?:->|=>)\s")
CODE_FENCE_RE = re.compile(r"```(?:sql|postgresql)?\s*(.*?)```", re.I | re.S)
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[A-Za-z_][\w.]*)\s*\((?P<body>.*?)\)\s*;?", re.I | re.S)
FROM_JOIN_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", re.I)


def literal(text: str) -> Any:
    text = text.strip().rstrip(".").replace("−", "-")
    text = re.sub(r"\btrue\b", "True", text, flags=re.I)
    text = re.sub(r"\bfalse\b", "False", text, flags=re.I)
    text = re.sub(r"\bnull\b", "None", text, flags=re.I)
    try:
        return ast.literal_eval(text)
    except Exception:
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        if re.fullmatch(r"-?\d+\.\d+", text):
            return float(text)
        raise


def split_top(value: str, sep: str = ",") -> list[str]:
    out: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == sep and depth == 0:
            out.append(value[start:index].strip())
            start = index + 1
    out.append(value[start:].strip())
    return [item for item in out if item]


def parse_example(example: str, params: list[str]) -> tuple[dict[str, Any], Any] | None:
    if not example or not ARROW_RE.search(example):
        return None
    parts = ARROW_RE.split(example, maxsplit=1)
    if len(parts) != 2:
        return None
    lhs, rhs = parts[0].strip(), parts[1].strip()
    lhs = re.sub(r"^(?:Input|Example)\s*:\s*", "", lhs, flags=re.I)
    try:
        expected = literal(rhs)
    except Exception:
        return None
    aliases = {"start": "starts", "end": "ends", "profit": "profits", "num": "nums"}
    values: dict[str, Any] = {}
    positional: list[Any] = []
    lhs = re.sub(r"\s+and\s+(?=[A-Za-z_]\w*\s*=)", ", ", lhs)
    for token in split_top(lhs):
        match = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", token, re.S)
        if match:
            name = aliases.get(match.group(1), match.group(1))
            try:
                values[name] = literal(match.group(2))
            except Exception:
                return None
        else:
            try:
                positional.append(literal(token))
            except Exception:
                return None
    for param in params:
        if param not in values and positional:
            values[param] = positional.pop(0)
    if positional:
        return None
    if set(params) - set(values):
        if len(params) == 1 and not values:
            try:
                return {params[0]: literal(lhs)}, expected
            except Exception:
                return None
        return None
    return {param: values[param] for param in params}, expected


def function_from_source(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return next((node for node in functions if node.name == "solve"), functions[0] if functions else None)


def execute_reference(source: str, function_name: str, kwargs: dict[str, Any]) -> tuple[bool, Any]:
    namespace = {"__name__": "reference_solution"}
    try:
        exec(compile(source, "<reference>", "exec"), namespace, namespace)
        function = namespace.get(function_name)
        if not callable(function):
            return False, None
        return True, function(**copy.deepcopy(kwargs))
    except Exception:
        return False, None


def mutate(value: Any, salt: int = 1) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + salt
    if isinstance(value, float):
        return value + salt
    if isinstance(value, str):
        if not value:
            return "a"
        return value + value[-1] if len(value) < 64 else value[::-1]
    if isinstance(value, list):
        if not value:
            return [salt]
        return value[1:] + value[:1] if len(value) > 1 else value + [copy.deepcopy(value[0])]
    if isinstance(value, tuple):
        return tuple(mutate(list(value), salt))
    if isinstance(value, dict):
        out = copy.deepcopy(value)
        for key in list(out)[:1]:
            out[key] = mutate(out[key], salt)
        return out
    return copy.deepcopy(value)


def python_spec(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    source = str(row.get("solution") or "")
    function = function_from_source(source)
    if function is None:
        return None, "no_function_entrypoint"
    params = [arg.arg for arg in function.args.args]
    if not params:
        return None, "zero_arg_entrypoint"
    parsed = parse_example(str(row.get("example") or ""), params)
    if not parsed:
        return None, "example_not_machine_parseable"
    kwargs, declared_expected = parsed
    ok, actual = execute_reference(source, function.name, kwargs)
    if not ok:
        return None, "reference_failed_public"
    if actual != declared_expected and not (isinstance(actual, tuple) and list(actual) == declared_expected):
        return None, "source_example_mismatch"
    tests = [{"id": "public-1", "name": "Source example", "visibility": "public", "input": kwargs, "expected_output": actual}]
    hidden = 0
    for salt in (1, 2, 3):
        candidate = {key: mutate(value, salt) for key, value in kwargs.items()}
        if candidate == kwargs:
            continue
        ok, expected = execute_reference(source, function.name, candidate)
        if not ok:
            continue
        hidden += 1
        tests.append({"id": f"hidden-{hidden}", "name": f"Hidden case {hidden}", "visibility": "hidden", "input": candidate, "expected_output": expected})
        if hidden >= 2:
            break
    if not hidden:
        return None, "no_valid_hidden_test"
    starter = f"def {function.name}({', '.join(params)}):\n    # Write your solution here\n    pass\n"
    return {
        "runtime": "python3.13",
        "starter_code": starter,
        "entrypoint": function.name,
        "tests": tests,
        "reference_validation": {"status": "passed", "public_tests": 1, "hidden_tests": hidden},
    }, "ready"


def extract_sql_solution(row: dict[str, Any]) -> str | None:
    solution = str(row.get("solution") or "")
    candidates = [block.strip() for block in CODE_FENCE_RE.findall(solution) if re.search(r"\b(?:SELECT|WITH)\b", block, re.I)]
    if candidates:
        return candidates[-1].rstrip(";") + ";"
    match = re.search(r"(?is)\b(WITH\b.*|SELECT\b.*)", solution)
    return match.group(1).strip().rstrip(";") + ";" if match else None


def sqlite_type(type_text: str) -> str:
    value = type_text.upper()
    if any(token in value for token in ("INT", "SERIAL")):
        return "INTEGER"
    if any(token in value for token in ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")):
        return "REAL"
    return "TEXT"


def parse_ddl(schema: str) -> dict[str, list[tuple[str, str]]]:
    blocks = CODE_FENCE_RE.findall(schema) or [schema]
    tables: dict[str, list[tuple[str, str]]] = {}
    for match in CREATE_TABLE_RE.finditer("\n".join(blocks)):
        name = match.group("name").split(".")[-1]
        columns: list[tuple[str, str]] = []
        for item in split_top(match.group("body")):
            if re.match(r"^(PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT)\b", item.strip(), re.I):
                continue
            column = re.match(r'^"?([A-Za-z_]\w*)"?\s+([^,]+)', item.strip(), re.S)
            if column:
                columns.append((column.group(1), column.group(2).strip()))
        if columns:
            tables[name] = columns
    return tables


def source_constants(query: str) -> tuple[list[int], list[str]]:
    numbers = [int(value) for value in re.findall(r"(?<![\w.])-?\d+(?![\w.])", query)[:8]]
    strings = re.findall(r"'([^']{1,32})'", query)[:8]
    return numbers, strings


def seed_for_tables(tables: dict[str, list[tuple[str, str]]], query: str) -> str:
    _numbers, strings = source_constants(query)
    statements: list[str] = []
    for table, columns in tables.items():
        for index in range(1, 7):
            values: list[Any] = []
            for column, type_text in columns:
                kind = sqlite_type(type_text)
                lower = column.lower()
                if kind == "INTEGER":
                    if lower == "id" or lower.endswith("_id"):
                        value = index if "customer" not in lower else (index % 3) + 1
                    elif any(token in lower for token in ("amount", "price", "revenue", "sales", "units", "qty", "count", "score", "salary")):
                        value = [5, 10, 20, 50, 100, 200][index - 1]
                    elif "year" in lower:
                        value = 2020 + index % 3
                    else:
                        value = index
                elif kind == "REAL":
                    value = float([5, 10, 20, 50, 100, 200][index - 1])
                elif "date" in lower or "time" in lower:
                    value = f"2024-01-0{index}"
                elif "status" in lower:
                    value = strings[0] if strings else ["active", "inactive"][index % 2]
                elif "category" in lower:
                    value = ["A", "B", "A", "C", "B", "A"][index - 1]
                elif "name" in lower:
                    value = f"name{index}"
                else:
                    value = strings[(index - 1) % len(strings)] if strings else f"v{index}"
                values.append(value)
            column_sql = ",".join(f'"{column}"' for column, _ in columns)
            literals = [str(value) if isinstance(value, (int, float)) else "'" + str(value).replace("'", "''") + "'" for value in values]
            statements.append(f'INSERT INTO "{table}" ({column_sql}) VALUES ({",".join(literals)});')
    return "\n".join(statements)


def sqlite_ddl(tables: dict[str, list[tuple[str, str]]]) -> str:
    return "\n".join(
        f'CREATE TABLE "{table}" (' + ", ".join(f'"{column}" {sqlite_type(type_text)}' for column, type_text in columns) + ");"
        for table, columns in tables.items()
    )


def sqlite_query(ddl: str, seed: str, query: str) -> tuple[bool, Any]:
    unsupported = r"\b(ILIKE|FILTER\s*\(|DATE_TRUNC|INTERVAL|GENERATE_SERIES|PERCENTILE|STRING_AGG|ARRAY_AGG|LATERAL|DISTINCT\s+ON)\b|::"
    if re.search(unsupported, query, re.I):
        return False, None
    try:
        connection = sqlite3.connect(":memory:")
        connection.executescript(ddl + "\n" + seed)
        cursor = connection.execute(query.rstrip(";"))
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, result, strict=True)) for result in cursor.fetchall()]
        connection.close()
        return True, rows
    except Exception:
        return False, None


def sql_spec(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    question_type = str(row.get("question_type") or "").lower()
    if "sql" not in question_type and str(row.get("subject") or "").lower() != "sql":
        return None, "not_sql_coding"
    tables = parse_ddl(str(row.get("input_output_or_schema") or ""))
    if not tables:
        return None, "ddl_not_extractable"
    query = extract_sql_solution(row)
    if not query:
        return None, "reference_sql_not_extractable"
    referenced = {name.split(".")[-1] for name in FROM_JOIN_RE.findall(query)}
    ctes = set(re.findall(r"(?i)(?:WITH|,)\s*([A-Za-z_]\w*)\s+AS\s*\(", query))
    referenced -= ctes
    if not referenced.issubset(set(tables)):
        return None, "reference_uses_undeclared_tables"
    ddl = sqlite_ddl(tables)
    seed = seed_for_tables(tables, query)
    ok, expected = sqlite_query(ddl, seed, query)
    if not ok:
        return None, "reference_not_sqlite_compatible"
    return {
        "dialect": "postgresql18",
        "starter_sql": "-- Write your PostgreSQL 18 query here.\n",
        "tests": [
            {"id": "public-1", "name": "Public dataset", "visibility": "public", "expected_output": expected},
            {"id": "hidden-1", "name": "Hidden dataset", "visibility": "hidden", "expected_output": expected},
        ],
        "challenge": {"ddl": ddl, "seed_data": seed, "expected_result": expected},
        "reference_sql": query,
        "reference_validation": {"status": "passed_local_sqlite_precheck", "public_tests": 1, "hidden_tests": 1, "requires_postgres_confirmation": True},
    }, "ready_precheck"


def pyspark_spec(row: dict[str, Any]) -> tuple[dict[str, Any], str]:
    return {
        "runtime": "pyspark",
        "tests": [],
        "fixture_status": "source_has_no_concrete_machine_fixture",
        "reference_code": row.get("solution"),
    }, "fixture_only"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    subjects: Counter[str] = Counter()
    runnable_subjects: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for line in args.input.open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        counts["rows"] += 1
        subject = str(row.get("subject") or "")
        subjects[subject] += 1
        spec: dict[str, Any] | None = None
        reason = "non_executable_question"
        if subject == "Python Coding":
            spec, reason = python_spec(row)
        elif subject == "SQL":
            spec, reason = sql_spec(row)
        elif subject == "PySpark":
            spec, reason = pyspark_spec(row)
        row["mode_specification"] = spec
        if spec and reason in {"ready", "ready_precheck"}:
            row["runnable"] = True
            row["execution_validation_status"] = "reference_validated" if reason == "ready" else "postgres_confirmation_pending"
            counts["runnable_candidates"] += 1
            runnable_subjects[subject] += 1
        else:
            row["runnable"] = False
            row["execution_validation_status"] = reason
        if subject == "PySpark" and spec:
            counts["pyspark_fixture_specs"] += 1
        reasons[reason] += 1
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    report = {
        "input_rows": counts["rows"],
        "output_rows": len(rows),
        "runnable_candidates": counts["runnable_candidates"],
        "pyspark_fixture_specs": counts["pyspark_fixture_specs"],
        "by_subject": dict(subjects),
        "runnable_by_subject": dict(runnable_subjects),
        "gating_reasons": dict(reasons),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "policy": {
            "python": "runnable only when source example parses and source reference solution passes public + generated hidden tests",
            "sql": "pre-runnable only when source DDL is complete and reference SQL passes deterministic local relational precheck; PostgreSQL confirmation required before publish as runnable",
            "pyspark": "fixture metadata only until a Spark runner and source-grounded concrete fixtures exist",
        },
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
