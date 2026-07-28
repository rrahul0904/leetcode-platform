# Multi-client + production infrastructure branch map

Start here when reviewing `feature/multiclient-production-foundation`:

- `MULTIPLATFORM_AUDIT.md` — repository baseline and ownership boundaries.
- `MOBILE_ARCHITECTURE.md` — native application design.
- `MOBILE_AUTH.md` — OIDC/PKCE/SecureStore.
- `MOBILE_EDITOR_ARCHITECTURE.md` — editor decision.
- `MOBILE_LOCAL_DEVELOPMENT.md` — simulator/device setup.
- `MOBILE_SECURITY_REVIEW.md` — native security review.
- `MULTIPLATFORM_TESTING.md` — test strategy.
- `PRODUCTION_INFRASTRUCTURE_AUDIT.md` — AWS baseline/gaps.
- `PRODUCTION_ARCHITECTURE.md` — target control/execution topology.
- `EXECUTION_SECURITY_MODEL.md` — hostile-workload threat boundary.
- `EXECUTION_STATE_MACHINE.md` — target async execution lifecycle.
- `NETWORK_SECURITY.md` — subnet/routing/metadata controls.
- `IAM_MODEL.md` — role/secret boundaries.
- `OBSERVABILITY.md` — metrics/alarms/redaction.
- `COST_CONTROLS.md` — execution/AI/storage cost guardrails.
- `DISASTER_RECOVERY.md` — restore-first recovery baseline.
- `INCIDENT_RESPONSE.md` — containment/runbook baseline.
- `PRODUCTION_DEPLOYMENT.md` — promotion and deployment gate.
- `PRODUCTION_ACCEPTANCE.md` — evidence-based release matrix.
- `IMPLEMENTATION_NOTES_MULTICLIENT_INFRA.md` — exact implemented vs blocked status.

The most important review fact is that AWS application compute remains disabled by default until the synchronous local execution path is replaced by the SQS/outbox/dispatcher design. This is a security gate, not unfinished configuration hidden behind optimistic documentation.
