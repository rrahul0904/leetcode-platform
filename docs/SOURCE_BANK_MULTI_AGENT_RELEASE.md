# Source-bank multi-agent release process

The reviewed source-backed bank has several gates that depend on different kinds of evidence. `scripts/source_bank_release_agents.py` turns those gates into independent agents with one fail-closed coordinator.

The coordinator does **not** change the immutable reviewed contract:

- normalized archive SHA-256: `9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b`
- source archives: 11
- searchable questions: 3,425
- company questions: 3,424
- company associations: 35,348
- statement-backed candidates: 121
- reference solutions: 120
- unique solution slugs: 1,063
- system-design resources: 29
- source CSV rows: 92,728
- reviewed Python fingerprints: 20

Missing evidence becomes `BLOCKED`. Contradictory evidence becomes `FAIL`. Nothing is promoted, repinned, substituted, or approved automatically.

## Agent topology

```text
                 ┌─────────────────────┐
                 │ Provenance Agent    │
                 │ 11 source archives  │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Corpus Agent        │
                 │ manifest + SHA      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Database Agent      │
                 │ import/idempotency  │
                 └─────────────────────┘

                 ┌─────────────────────┐
                 │ Rights Agent        │
                 │ governance evidence │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Run/Submit Agent    │
                 │ execution + E2E     │
                 └─────────────────────┘

          Provenance and Rights run concurrently.
          Dependency chains then advance independently.
```

## 1. Provenance agent

The provenance agent reads `content/imported/source-backed/source-lock.json` and counts pinned release-grade sources plus exact original source ZIPs supplied at runtime.

Current locked Git evidence is still 9/11. If the two missing original files are recovered, place them in one directory using their exact names:

```text
LeetCode-Solutions-master.zip
Competitive-Programming-master.zip
```

Run:

```bash
uv run python scripts/source_bank_release_agents.py \
  --source-archive-dir /secure/recovered-source-zips
```

The agent verifies the upload-derived fingerprint before treating either ZIP as usable evidence. For the JavaScript archive it checks the raw ZIP boundary, useful/code counts, MIT license signature, and README catalog shape. For the Competitive Programming archive it checks the raw ZIP boundary plus useful/C++ counts. Near matches fail rather than being substituted.

Supplying an original ZIP does not silently rewrite `source-lock.json`; it is recorded as runtime evidence in the agent report so a reviewer can decide whether to promote that evidence into the permanent lock.

## 2. Corpus agent

The corpus agent has two valid routes.

### Route A — deterministic 11-source reconstruction

When the provenance agent has effective 11/11 evidence, the corpus agent materializes pinned Git sources plus any exact recovered source ZIPs, runs the existing deterministic builder, requires the exact reviewed manifest, creates the deterministic normalized ZIP, and requires the immutable reviewed SHA.

Any manifest or SHA difference is `FAIL`.

### Route B — exact reviewed corpus artifact

If the exact normalized corpus was retained elsewhere, provide it directly:

```bash
uv run python scripts/source_bank_release_agents.py \
  --reviewed-corpus /secure/rigor_source_backed_question_bank.zip
```

A raw ZIP or base64 representation is accepted only when its decoded bytes hash to the immutable reviewed SHA. This can close the corpus/database path while raw 11/11 provenance remains a separate gate.

Use `--install` only after exact SHA validation to write the verified base64 corpus to the normal source-bank install target.

## 3. Database agent

When the corpus agent passes, supply a **clean PostgreSQL database URL**:

```bash
RIGOR_DATABASE_URL='postgresql+psycopg://...' \
uv run python scripts/source_bank_release_agents.py \
  --reviewed-corpus /secure/rigor_source_backed_question_bank.zip
```

The database agent delegates to `verify_source_bank_release.py`. It requires:

- first import status `completed`;
- repeat import status `already_imported`;
- the same corpus identity on both imports;
- exactly 3,425 searchable questions;
- exactly 3,424 company questions;
- exactly 35,348 company associations;
- exactly 121 statement-backed questions;
- exactly 120 reference solutions;
- exactly 29 system-design resources;
- one canonical completed import record;
- zero duplicate problems, company associations, or system-design rows.

Without a clean database URL the agent stays `BLOCKED`; it does not claim idempotency from unit tests alone.

## 4. Rights agent

The rights agent always reconstructs and checksum-verifies the 20 quarantined `IMP-*` Python review packages. It never turns public GitHub availability into hosting permission.

Publication can advance only when an **external governance approval file** is supplied. Schema:

```json
{
  "schema_version": 1,
  "approvals": [
    {
      "package_id": "IMP-0007",
      "rights_disposition": "hostable_licensed",
      "publication_approved": true,
      "approved_by": "<real reviewer identity>",
      "approved_at": "<review timestamp>",
      "license_identifier": "<verified license or grant>",
      "evidence": ["<real rights evidence>"],
      "modification_rights": true,
      "export_rights": true
    }
  ]
}
```

Run:

```bash
uv run python scripts/source_bank_release_agents.py \
  --approval-file /secure/source-bank-governance-approval.json
```

The file is treated as externally supplied governance evidence. The agent validates completeness; it does not independently grant legal rights and does not fabricate approval.

## 5. Run → Submit agent

An approved package must first pass its own executable reference tests. That is necessary but not sufficient for the end-to-end gate.

The final agent additionally requires evidence from an actual source-backed Run → Submit exercise through the existing execution path (`rigor_api.execution_api.queue_run` and `queue_submit`). The proof JSON must contain:

```json
{
  "schema_version": 1,
  "package_id": "IMP-0007",
  "run": {
    "status": "COMPLETED",
    "public_tests_passed": true
  },
  "submit": {
    "status": "COMPLETED",
    "hidden_total": 4,
    "hidden_passed": 4
  },
  "idempotency": {
    "run_duplicate": true,
    "submit_duplicate": true
  }
}
```

Run:

```bash
uv run python scripts/source_bank_release_agents.py \
  --approval-file /secure/source-bank-governance-approval.json \
  --run-submit-proof /secure/source-backed-run-submit-proof.json
```

The proof only passes when the package is one of the externally approved reviewed packages, Run completes and passes public tests, Submit completes and passes at least one hidden test, and duplicate Run/Submit requests demonstrate the idempotency contract.

## Modes

Normal mode is an audit. It writes one JSON file per agent and a consolidated report under `.work/source-bank-release-agents/`, then exits zero even when legitimate external blockers remain.

```bash
make release-agents
```

Strict mode is the full fail-closed release gate. Any `BLOCKED` or `FAIL` returns non-zero.

```bash
make release-agents-enforce
```

Inputs can be passed through Make variables:

```bash
make release-agents-enforce \
  SOURCE_ARCHIVE_DIR=/secure/recovered-source-zips \
  REVIEWED_CORPUS=/secure/rigor_source_backed_question_bank.zip \
  RELEASE_DATABASE_URL='postgresql+psycopg://...' \
  GOVERNANCE_APPROVAL=/secure/source-bank-governance-approval.json \
  RUN_SUBMIT_PROOF=/secure/source-backed-run-submit-proof.json
```

`REVIEWED_CORPUS` and `SOURCE_ARCHIVE_DIR` are alternative ways to advance the normalized corpus path; providing both is allowed, but the exact reviewed corpus route takes precedence for corpus construction while provenance is still reported independently.

## CI

`.github/workflows/source-bank-release-agents.yml` runs the coordinator in audit mode on the exact PR head. The workflow is successful when agents run correctly and the remaining state is `PASS` or `BLOCKED`. A hard `FAIL` makes the workflow fail.

The artifact `source-bank-release-agent-report` contains:

- `provenance.json`
- `corpus.json`
- `database.json`
- `rights.json`
- `run-submit.json`
- `report.json`

This gives future release work a durable handoff instead of relying on chat history or one-off forensic scripts.
