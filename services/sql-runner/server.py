from __future__ import annotations

import json
import os
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any, cast
from uuid import UUID

import psycopg
from runner import RunnerInfrastructureError, RunnerInputError, parse_request, run_request

MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
# The SQL runner resets a dedicated execution database and candidate role for
# every test. Serial execution prevents one local attempt from replacing another
# attempt's fixture while still keeping application PostgreSQL completely separate.
CAPACITY = BoundedSemaphore(1)


def _failure(
    *,
    execution_id: str,
    attempt: int,
    category: str,
    exit_code: int = 2,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution_id": execution_id,
        "attempt": max(1, attempt),
        "status": "FAILED",
        "runtime_ms": 0,
        "exit_code": exit_code,
        "tests": [],
        "stdout": "",
        "stderr": "",
        "error_category": category,
    }


class RunnerHandler(BaseHTTPRequestHandler):
    server_version = "RigorSqlRunner/1"

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = json.dumps(
                _failure(
                    execution_id=str(payload.get("execution_id") or "unknown"),
                    attempt=int(payload.get("attempt") or 1),
                    category="runner_response_limit",
                    exit_code=3,
                ),
                separators=(",", ":"),
            ).encode("utf-8")
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path != "/healthz":
            self._json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
            return
        self._json(HTTPStatus.OK, {"status": "ok", "runtime": "postgresql"})

    def do_POST(self) -> None:
        if self.path != "/run":
            self._json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
            return
        length_value = self.headers.get("Content-Length", "")
        try:
            length = int(length_value)
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "invalid_content_length"})
            return
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"status": "request_too_large"})
            return
        try:
            raw = self.rfile.read(length)
            decoded: object = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"status": "invalid_json"})
            return
        if not isinstance(decoded, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"status": "invalid_payload"})
            return
        payload = cast(dict[str, Any], decoded)
        execution_text = str(payload.get("execution_id") or "")
        attempt_value = payload.get("attempt")
        attempt = (
            attempt_value
            if isinstance(attempt_value, int) and not isinstance(attempt_value, bool)
            else 1
        )
        try:
            execution_id = UUID(execution_text)
        except ValueError as exc:
            self._json(
                HTTPStatus.OK,
                _failure(
                    execution_id=execution_text or "00000000-0000-0000-0000-000000000000",
                    attempt=attempt,
                    category=exc.__class__.__name__,
                ),
            )
            return

        if not CAPACITY.acquire(blocking=False):
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                _failure(
                    execution_id=str(execution_id),
                    attempt=attempt,
                    category="runner_capacity_exceeded",
                    exit_code=3,
                ),
            )
            return
        try:
            temp_root = Path("/workspace/tmp")
            temp_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=temp_root,
                delete=True,
            ) as request_file:
                json.dump(payload, request_file, separators=(",", ":"), ensure_ascii=False)
                request_file.flush()
                parsed = parse_request(Path(request_file.name), execution_id)
                result = run_request(parsed)
            result["execution_id"] = str(execution_id)
            self._json(HTTPStatus.OK, cast(dict[str, object], result))
        except RunnerInputError as exc:
            self._json(
                HTTPStatus.OK,
                _failure(
                    execution_id=str(execution_id),
                    attempt=attempt,
                    category=exc.__class__.__name__,
                ),
            )
        except (RunnerInfrastructureError, psycopg.Error):
            self._json(
                HTTPStatus.OK,
                _failure(
                    execution_id=str(execution_id),
                    attempt=attempt,
                    category="runner_infrastructure_error",
                    exit_code=3,
                ),
            )
        except Exception:
            self._json(
                HTTPStatus.OK,
                _failure(
                    execution_id=str(execution_id),
                    attempt=attempt,
                    category="runner_infrastructure_error",
                    exit_code=3,
                ),
            )
        finally:
            CAPACITY.release()


def main() -> int:
    host = os.getenv("RIGOR_RUNNER_HOST", "0.0.0.0")
    port = int(os.getenv("RIGOR_RUNNER_PORT", "8082"))
    server = ThreadingHTTPServer((host, port), RunnerHandler)
    server.serve_forever(poll_interval=0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
