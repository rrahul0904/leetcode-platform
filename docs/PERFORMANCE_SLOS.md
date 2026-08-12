# Performance and capacity baselines

These targets separate repeatable local evidence from production commitments.

## Measurement command

```bash
make bootstrap
make capacity-local
```

Generated evidence:

- `artifacts/capacity/runner-capacity.json`
- `artifacts/capacity/container-stats.txt`
- `artifacts/capacity/capacity-summary.json`
- `artifacts/bootstrap-seconds.txt` when CI records bootstrap duration

The benchmark executes controlled traffic at declared runner concurrency and burst traffic above it. Capacity rejections are reported as explicit backpressure, not merged into infrastructure failures.

## Local release objectives

Reference runner: GitHub-hosted Ubuntu runner or a developer machine with at least four logical CPUs, 8 GB RAM, Docker Engine, and no competing heavy workload.

| Signal | Local objective | Release interpretation |
|---|---:|---|
| Clean populated bootstrap | p95 ≤ 180 seconds | Regression guard, not a user-facing SLO |
| Controller heartbeat age | < 15 seconds while healthy | Readiness and alert input |
| Oldest visible queued job | p95 < 5 seconds steady; < 30 seconds during a bounded burst | Indicates queue pressure |
| Controlled Python scenario | 100% completed; zero infrastructure errors | At or below declared concurrency |
| Controlled SQL scenario | 100% completed; zero infrastructure errors | At or below declared concurrency |
| Burst behavior | Explicit completion or HTTP 503 capacity rejection | No silent timeout or unbounded queueing |
| Controller restart recovery | Terminal state within 45 seconds after lease expiry | Tested with shortened CI leases |
| Running cancellation | Durable `CANCELLED` immediately; runner resource released by timeout bound | Local Docker limitation remains visible |
| Backup and restore | Checksum, schema, representative counts, and post-restore readiness all pass | Required local release gate |

The first successful reliability run establishes the observed baseline. Later changes should compare the same scenario and hardware class rather than substituting anecdotal timings.

## Provisional production SLOs

These are design targets only until a staging environment produces sustained evidence.

| Service indicator | Proposed objective |
|---|---:|
| API availability excluding planned maintenance | 99.9% monthly |
| Execution acceptance latency | p95 < 300 ms |
| Queue-to-runner start latency under normal load | p95 < 5 seconds |
| Python execution infrastructure success | ≥ 99.5% excluding candidate failures/timeouts |
| SQL execution infrastructure success | ≥ 99.5% excluding candidate failures/timeouts |
| Controller recovery from a single replica loss | p95 < 30 seconds |
| Cancellation acknowledgement | p95 < 1 second |
| Forceful sandbox termination after cancellation | p95 < 5 seconds |
| Execution result availability after runner completion | p95 < 2 seconds |
| Restore point objective | ≤ 15 minutes |
| Restore time objective | ≤ 60 minutes |

## Capacity planning before a candidate cohort

Before inviting a meaningful cohort:

1. Run staged load at 1×, 2×, and 4× forecast peak concurrency.
2. Measure queue age, runner scheduling latency, CPU, memory, database connections, image-pull time, retry rate, and result persistence latency.
3. Confirm backpressure returns bounded, retryable responses before database or runner saturation.
4. Validate autoscaling cooldowns and minimum warm capacity.
5. Re-run the workload with one controller replica terminated, one execution node drained, and one availability zone unavailable.
6. Set alert thresholds from observed saturation curves and error-budget policy.

No local Docker measurement proves production Kubernetes or gVisor capacity.
