# Local observability

The observability profile is optional and does not change the default Docker topology.

## Start

```bash
make bootstrap
make observability-local
make verify-observability
```

Surfaces:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3002`
- OTLP/gRPC: `localhost:4317`
- OTLP/HTTP: `localhost:4318`

Grafana provisions the **Rigor Local Execution** dashboard automatically.

## Metrics

The `execution-metrics` service connects with the read-only application role and exposes:

- visible queue depth;
- in-flight messages hidden by visibility leases;
- age of the oldest visible job;
- active dispatching/running executions;
- configured runner capacity and saturation ratio;
- durable retry count;
- maximum-attempt exhaustion count;
- controller heartbeat age;
- Python and SQL runner readiness;
- recent p50, p95, and p99 execution duration;
- terminal status counts;
- error-category counts.

The exporter does not expose candidate source, inputs, expected answers, access tokens, or user identifiers.

## Correlation IDs

The API accepts or generates `X-Correlation-ID`. Authentication projects that value into the authenticated principal. Execution creation persists it as `execution_requests.trace_id`; the transactional outbox carries the same value; controller structured log fields include both `trace_id` and `execution_id`.

Use `trace_id` to follow request acceptance into controller events. Use `execution_id` for durable aggregate, queue, runner, and result investigation. Neither identifier should contain personal data.

The OpenTelemetry Collector accepts OTLP traces, metrics, and logs for local integration testing. The current local application continues to emit structured process logs; production should attach the approved OTLP exporter and central log destination through managed configuration rather than embedding collector credentials in application images.

## Suggested alerts

Local alerts are diagnostic guidance, not production paging policy:

- controller heartbeat age greater than 15 seconds;
- Python or SQL runner readiness equal to zero for 30 seconds;
- oldest visible queue age greater than 30 seconds;
- runner saturation above 0.85 for five minutes;
- maximum-attempt exhaustion greater than zero;
- p95 duration above the SLO for 10 minutes.

Production alert thresholds must be validated against staging traffic and error budgets.
