# API Specification

The FastAPI-generated OpenAPI document is canonical. MVP endpoints use `/api/v1`; breaking contracts require `/api/v2`.

## Foundation endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/livez` | process liveness |
| GET | `/readyz` | dependency readiness |
| GET | `/metrics` | protected/scraped telemetry |
| GET | `/api/v1/questions` | paginated published catalog with filters |
| GET | `/api/v1/questions/{slug}` | versioned candidate-safe detail |
| GET/PUT | `/api/v1/profile` | authenticated profile and onboarding |
| POST | `/api/v1/submissions` | idempotent submission request |
| GET | `/api/v1/submissions/{id}` | result and evidence state |
| POST | `/api/v1/admin/question-versions` | permissioned authoring |
| POST | `/api/v1/admin/question-versions/{id}/transition` | controlled review transition |

Collection responses contain `items`, `page`, `page_size`, `total`, and `has_next`. Errors contain `code`, `message`, `correlation_id`, `field_errors`, and `retryable`. Mutating requests accept `Idempotency-Key`; responses expose correlation and rate-limit headers.

Candidate endpoints never expose interviewer instructions, hidden tests, private rubrics before submission, or reference solutions before the configured reveal state.

