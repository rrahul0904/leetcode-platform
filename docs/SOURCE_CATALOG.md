# External Source-Backed Competency Catalog

Verified: 2026-07-21

## Collection rule

Rigor collects only question-reference metadata made available through an official API or an explicitly licensed public repository. The collector never stores external problem statements, answers, solutions, tests, premium fields, or user profiles. External references remain separate from original hosted questions.

The machine-readable review record is [`content/sources/source-policy.json`](../content/sources/source-policy.json). Every automated connector must be reviewed, approved, domain-bound, and limited to its recorded coverage level before synchronization.

## First backfill

| Source | Access basis | References | Stored fields |
| --- | --- | ---: | --- |
| Exercism | Official MIT-licensed track repositories | 1,127 | Canonical URL, title, track, difficulty where present, concepts, prerequisites, status |
| Stack Overflow | Official Stack Exchange API and CC BY-SA metadata | 967 | Canonical URL, title, tags, content-license identifier, aggregate counters |
| Software Engineering Stack Exchange | Official Stack Exchange API and CC BY-SA metadata | 295 | Canonical URL, title, tags, content-license identifier, aggregate counters |
| GitHub | Official API plus MIT-licensed allowlist | 142 | Repository exercise path, title derived from slug, SPDX license, canonical URL |
| Codewars | Official v1 API with documented identifiers | 3 | Canonical URL, title, rank, tags, languages, aggregate counters |
| **Total** |  | **2,534** | **5,990 competency mappings** |

## Blocked and paused sources

- **LeetCode:** blocked. Its Terms of Service expressly prohibit crawling, scraping, and spidering.
- **HackerRank:** blocked. Its terms reserve service content and prohibit copying, derivative use, and competitive analysis.
- **Reddit:** paused. The Data API requires registered access, approved-use compliance, retention/deletion controls, and additional permission for commercial or AI-related use.
- **NeetCode, DataLemur, StrataScratch, and Interview Query:** discovery-only and disabled until a bulk metadata API, reusable license, or written permission is verified.

Deep links may be added manually only when the source policy permits them. A page being publicly viewable does not by itself authorize automated collection.

## Competency mapping

The connector normalizes source tags and concepts into the seeded 28-competency ontology and records patterns separately. Mappings are transactional: an unknown competency rejects the sync rather than silently creating a taxonomy entry.

The first backfill exposed zero-reference gaps in AI evaluation, AI infrastructure, AI safety, behavioral competencies, data architecture, engineering management, experimentation, generative AI, observability, principal engineering, recommendation systems, staff engineering, and technical leadership.

The first source-backed original batch therefore contains:

- `PY-0002`: dependency-aware data backfill planning (`data-architecture`)
- `PY-0003`: idempotent event-time counting (`observability`)
- `PY-0004`: AI evaluation window indexing (`ai-evaluation`, `experimentation`)

These are original hosted drafts with solutions, executable reference tests, public/hidden test specifications, rubrics, and provenance. They remain in `awaiting_technical_review`; none is automatically published.

## Operation

```bash
SSL_CERT_FILE="$PWD/.docker-build-ca.pem" ./scripts/collect-external-references \
  --ca-file "$PWD/.docker-build-ca.pem"
```

Docker operators can rebuild the API image and run the one-shot catalog profile:

```bash
docker compose build api
docker compose --profile catalog run --rm catalog
```

Repeated runs are idempotent upserts. Source counts, synchronization timestamps, audit events, mappings, and refreshed coverage-gap briefs are persisted in PostgreSQL.
