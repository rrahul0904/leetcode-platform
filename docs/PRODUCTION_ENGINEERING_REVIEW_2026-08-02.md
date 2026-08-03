# Production engineering review — merge `b77e70c`

Reviewed commit: `b77e70c179da4fdbcc938fbe19e6b1cfb73a8e95`

Scope: local Docker lifecycle, execution durability, runner boundaries, PostgreSQL 18 recovery, security controls, CI evidence, and documentation accuracy.

## Findings

### P0

None.

### P1

None for the documented trusted local-development boundary.

### P2 — running local cancellation is bounded, not forceful

`apps/api/src/rigor_api/local_execution_controller.py:369-374`

The local controller removes the future from its in-memory registry and calls `Future.cancel()`. Python futures cannot cancel a callable that has already started, so an already-running runner HTTP request continues until the runner's bounded subprocess timeout completes. The durable aggregate is still moved to `CANCELLED`, and late results cannot overwrite that terminal state, but local resource release is not immediate.

Concrete failure path: cancel a CPU-bound execution after the runner has started. Candidate-visible state becomes `CANCELLED`, while the runner remains occupied until its configured timeout. This is acceptable for the trusted local Docker boundary and must not be represented as production-grade termination.

Mitigation in the follow-up branch:

- browser failure injection verifies queued and running cancellation;
- the cancelled durable state is rechecked after the runner timeout window;
- production SLOs require forceful Kubernetes Job deletion and gVisor evidence.

### P2 — no browser or accessibility release evidence

`apps/web/package.json:5-11`

The merged Web package exposed lint, typecheck, Vitest, and build commands only. There was no browser automation or automated WCAG check, leaving routing, local OIDC, onboarding, Run/Submit polling, result rendering, mock exams, learning paths, and keyboard behavior outside CI.

Mitigation in the follow-up branch:

- Chromium Playwright journeys through the real Docker application;
- axe-core checks WCAG 2 A/AA and WCAG 2.1 A/AA;
- serious and critical violations fail the reliability workflow;
- browser evidence and failure screenshots are retained as workflow artifacts.

### P2 — execution resilience paths were implemented but not fault-injected

`apps/api/src/rigor_api/execution_controller.py:162-260` and `apps/api/src/rigor_api/execution_controller.py:560-690`

The controller implemented durable claims, message visibility renewal, expired-lease reconciliation, stale queued republishing, retries, maximum attempts, cancellation, and terminal cleanup. The merged checks validated healthy-path execution but did not kill the controller, stop runners, replay duplicate messages, exhaust retries, or restart the disposable SQL database.

Mitigation in the follow-up branch adds automated evidence for:

- controller termination and expired-lease recovery;
- duplicate queue delivery;
- transient and sustained Python runner loss;
- maximum-attempt exhaustion;
- queued and running cancellation;
- disposable SQL database restart.

### P2 — no operational metrics or capacity baseline

`apps/api/src/rigor_api/local_execution_controller.py:403-440`

The controller heartbeat persisted queue depth and runner readiness, but there was no scrape endpoint, dashboard, latency quantiles, oldest-job age, retry/dead-letter view, saturation measure, or repeatable throughput test.

Mitigation in the follow-up branch adds:

- a read-only Prometheus exporter;
- Prometheus, Grafana, and OpenTelemetry Collector profiles;
- a provisioned execution dashboard;
- controlled and burst runner capacity scenarios;
- container CPU, memory, and PID snapshots;
- local and provisional production SLOs.

### P3 — merged queue depth mixed visible and in-flight work

`apps/api/src/rigor_api/local_execution_controller.py:129-135`

`LocalExecutionQueueClient.depth()` counted every queue row, including messages hidden by an active visibility timeout. That value is useful as total durable backlog but ambiguous as ready-to-dispatch depth.

Mitigation in the follow-up exporter reports separate visible and in-flight gauges and exposes oldest visible-message age.

## Verified strengths

- Candidate source never executes in the Web or FastAPI processes.
- Python and SQL runners are reachable only through the internal execution network.
- Runners receive no application PostgreSQL credentials, cloud credentials, Docker socket, or host bind mounts.
- Candidate SQL uses a separate disposable PostgreSQL 18 service.
- Containers use read-only filesystems where practical, dropped capabilities, `no-new-privileges`, bounded memory, CPU, PIDs, request size, result size, and execution time.
- The application database remains durable and separately backed up.
- Restore preserves archive ownership and validates the migration role before restarting the application.
- Local Docker execution fails closed outside local/development configuration.
- Idempotency uses a durable key plus request hash and detects conflicting reuse.
- Exact-head CI validated Web, Python, migrations, Compose, images, scans, SBOMs, Terraform, Packer, bootstrap, execution health, backup, and restore.

## Verdict

The merged implementation is safe to remain on `main` as a dependable local Docker application.

It is not yet a production SaaS release. Live staging, managed secrets, alert delivery, production backup policy, traffic testing, candidate cohort validation, and operational runbooks still require environment evidence.

It is not production-grade isolation for untrusted code. Docker Compose on a trusted workstation is not equivalent to dedicated Kubernetes execution nodes using gVisor, restrictive network policies, workload identity denial, and live adversarial verification.
