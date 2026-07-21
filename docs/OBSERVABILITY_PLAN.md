# Observability Plan

OpenTelemetry instruments browser navigation, Next.js server work, FastAPI requests, PostgreSQL, Temporal, AI gateway calls, WebSockets, executions, content publication, authentication, and administration. Correlation IDs cross every trusted boundary; candidate-visible errors expose safe IDs only.

Initial SLO proposals—subject to load testing—are 99.9% monthly availability for catalog APIs, p95 catalog latency below 300 ms excluding client network, and 99% of accepted execution requests reaching a terminal state within their declared timeout plus startup budget. No SLO is claimed until measured.

Dashboards cover API/web performance, database/cache health, workflow failures, model latency/cost, sandbox queues/startup/timeouts, submission results, content failures, interviews, plans, auth, and billing webhooks. Alerts must link to an owner and runbook.

