# Reliability testing

The `Reliability evidence` workflow runs against the populated Docker application with shortened test-only execution leases.

## Browser coverage

Chromium Playwright validates:

- keyboard-only local candidate sign-in;
- candidate onboarding and profile persistence;
- hosted problem selection;
- practice workspace creation;
- asynchronous Run and Submit;
- result rendering and deterministic submission evaluation;
- mock-exam intro, keyboard start, and exam navigator;
- learning-path navigation;
- question-bank keyboard tab activation.

axe-core runs WCAG 2 A/AA and WCAG 2.1 A/AA rules on the principal candidate surfaces. Serious and critical violations fail CI. JSON reports and a failure screenshot are uploaded with the workflow evidence.

The browser suite uses the real local OIDC provider, API, PostgreSQL, controller, and runners. It does not replace API or component tests.

## Failure injection

The same workflow verifies:

| Scenario | Required evidence |
|---|---|
| Duplicate delivery | Replayed queue events drain without changing terminal attempt count |
| Controller restart | A running execution loses its in-memory handle, the lease expires, reconciliation retries it, and a terminal state is reached |
| Expired lease | Attempt count increases through durable reacquisition rather than an in-memory retry |
| Transient Python runner loss | Runner outage produces an infrastructure retry and completes after runner recovery |
| Sustained Python runner loss | The aggregate terminates as failed after the configured maximum attempts |
| Queued cancellation | Cancellation persists while the controller is stopped and remains terminal after restart |
| Running cancellation | Candidate-visible state becomes and remains `CANCELLED` while the bounded local runner finishes independently |
| SQL database restart | The disposable execution database and SQL runner return healthy and execute a fixture-backed smoke query |

## Local execution limitation

The local controller stores active runner calls in process memory. Restarting it deliberately loses those in-memory futures so durable lease reconciliation is exercised. Cancellation calls `Future.cancel()`, which cannot terminate a callable already running; the subprocess timeout remains the resource bound.

Production must use Kubernetes Job deletion, pod termination grace limits, RuntimeClass evidence, and gVisor isolation. Passing this workflow does not satisfy those production controls.

## Evidence artifacts

The workflow uploads:

- execution snapshots for each failure scenario;
- axe reports;
- failure screenshots and stack traces;
- Prometheus scrape and query output;
- bootstrap duration;
- runner throughput and latency quantiles;
- container CPU, memory, and PID snapshots;
- queue, controller, terminal-state, and service-log diagnostics.
