# REA — Epireum Data Engineering Lab (2026-10-20)

## Provenance, classification and rights

- Reddit post: https://www.reddit.com/r/dataengineering/comments/1xa0uo1/data_engineering_lab_to_practice_on_your_laptop/
- Reference site: https://maarthala.github.io/data-engineering-lab/
- Reference repository: https://github.com/maarthala/data-engineering-lab
- Inspected upstream SHA: `ad2804fcd93ffe738828b226f918f5314a452ac1`
- Ownership: **DONOR/EXTENSION**, not a new standalone product. Absorb into existing SkillForge/LeetCode Data Engineering path.
- GitHub reported no repository-level license and no root LICENSE in the upstream tree at intake. Treat content, assets, code and curricula as **all-rights-reserved absent explicit permission**. The code and synthetic feed in this PR are independently authored; do not copy upstream artifacts.

## Evidence-based capability routing

| Donor capability | SkillForge treatment | State |
| --- | --- | --- |
| Guided Bronze/Silver/Gold work | Original interactive browser-only pipeline exercise | P0 candidate |
| SQL/Python skills and progress | Existing canonical question bank, runner and evidence | Already exists; hosted proof separate |
| Incremental ingestion, upserts, SCD2 and replay | Separate graded author-owned challenge packages | P1 backlog |
| Spark, Parquet, Iceberg | Opt-in local isolated lab with synthetic fixtures | P2, blocked |
| Airflow, dbt, BI and catalog | Adapter-based capstone exercises; no new grading or identity stack | P3, blocked |
| Teams, SSO, secret vault and governance | Existing identity + independent tenant/security certification | P3, blocked |
| Cloud competency mapping | Original curriculum rubrics and platform alternatives | P4, gated |

## What P0 actually implements

`/data-engineering-lab` is an original candidate-facing browser exercise with editable CSV and actionable feedback, not a static clone or distributed runtime.

- **Bronze**: bounded CSV parser, exact source header and raw order rows (500 rows / 100 KB max).
- **Silver**: strict identifiers, UTC timestamps, integer quantities, cents-safe USD amounts, exact duplicate delivery handling and conflicting event quarantine.
- **Gold**: deterministic date-by-SKU counts, quantity and revenue aggregates with stable ordering.
- **Exercise**: fix a negative quantity and rerun, inspect each stage; quality status reflects real transformation output.
- No fetch calls, uploads, remote code execution, secret storage, user database writes or score claims.

Tests verify the original sample, repair, idempotent duplicates, conflicting duplicates, malformed CSV, bad timestamps, invalid IDs/money/quantities, input limits and determinism. These tests certify only the pure browser engine.

## Remaining acceptance gates

**P1**: validated package-schema SQL/Python incremental-processing capstones, source fixtures + authoritative hidden tests, shared isolated runner, reviewer and release receipts.

**P2**: local opt-in Spark/Iceberg service; bounded hardware budget, reset/replay, credentials, network and failure isolation; synthetic datasets only.

**P3**: Airflow/dbt, BI/catalog, teams, SSO and vault; demonstrate tenant RLS, DAG/access isolation, credential protections and rollback. No production writes until approved.

**P4**: independent technical and copyright review, exact SHA CI/browser UAT, staging adversarial evaluation, deployment proof, operational recovery and production release gate.

Existing `docs/DATAFORGE_CAPABILITY_MAP.md` explicitly reports 19 source-backed PySpark exercises and 0 runnable ones. This PR does not change those counts. Existing hosted release candidate PR #66 and production issue #55 are separate and remain gated.

**Do not claim end-to-end platform completion from P0 code.** Only observed test receipts and real hosted validation count.