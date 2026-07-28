# Rigor observability baseline

## Trusted services

Use structured logs, traces, and metrics. Candidate source, hidden tests, credentials, and raw private profile data are excluded from telemetry by default.

Correlation identifiers should include, where policy permits:

- request_id;
- candidate_id;
- organization_id;
- practice_session_id;
- submission_id;
- execution_id;
- interview_id.

Do not use uncontrolled high-cardinality identifiers as CloudWatch metric dimensions.

## Implemented infrastructure alarms

Terraform currently alarms on:

- execution queue depth;
- execution oldest-message age;
- execution DLQ activity;
- RDS CPU;
- RDS free storage;
- Valkey engine CPU.

Each environment creates a separate SNS alert topic. Subscriptions/routing into the operational incident system are intentionally environment-specific and remain to be configured.

## Metrics required with async execution

When the dispatcher is implemented add:

- API execution request rate;
- outbox age/publish failures;
- dispatch latency;
- sandbox startup time;
- execution runtime;
- completion/failure/timeout/infrastructure-error rates;
- SQL PostgreSQL startup time;
- gVisor launch failures;
- cleanup/reconciliation failures;
- CPU-seconds and cost attribution.

## Client telemetry

Web/native should report crashes, startup/auth/API/navigation/editor/draft/submission failures without collecting full candidate source by default.

## OpenTelemetry

The backend already includes OpenTelemetry SDK dependencies. Exporter/backend selection, sampling policy, trace/log correlation, redaction tests, and production destination are outstanding and must be established before observability is considered production complete.
