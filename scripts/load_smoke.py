#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
import urllib.error
import urllib.request


def request_once(url: str, timeout: float) -> tuple[bool, float, str]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "skillforge-launch-load-smoke/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            elapsed = (time.perf_counter() - started) * 1000
            return 200 <= response.status < 400, elapsed, str(response.status)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return False, elapsed, type(exc).__name__


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("inf")
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percent))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--p95-ms", type=float, default=2500.0)
    parser.add_argument("--max-failures", type=int, default=0)
    args = parser.parse_args()

    if args.requests <= 0 or args.concurrency <= 0:
        raise SystemExit("requests and concurrency must be positive")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(
            pool.map(
                lambda _: request_once(args.url, args.timeout_seconds),
                range(args.requests),
            )
        )

    failures = [result for result in results if not result[0]]
    latencies = [result[1] for result in results if result[0]]
    p50 = statistics.median(latencies) if latencies else float("inf")
    p95 = percentile(latencies, 0.95)
    maximum = max(latencies, default=float("inf"))

    print(
        f"url={args.url} requests={args.requests} concurrency={args.concurrency} "
        f"success={len(latencies)} failures={len(failures)} "
        f"p50_ms={p50:.1f} p95_ms={p95:.1f} max_ms={maximum:.1f}"
    )
    if failures:
        print("failure_samples=" + ",".join(result[2] for result in failures[:10]))

    if len(failures) > args.max_failures:
        print(f"FAIL: failures {len(failures)} > allowed {args.max_failures}")
        return 1
    if p95 > args.p95_ms:
        print(f"FAIL: p95 {p95:.1f}ms > threshold {args.p95_ms:.1f}ms")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
