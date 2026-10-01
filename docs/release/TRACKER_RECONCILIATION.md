# Reverse-engineering tracker reconciliation

Audit date: 2026-10-01. Repository baseline: `403b28afe7498e273c5183adbea8da274af72017`.

## Existing canonical rows and repository evidence

| Canonical row | Current repository mapping | Evidence | Action |
| --- | --- | --- | --- |
| RE-020 Layrs AI Tutor | Layrs tutor capability in Rigor | `docs/tutor/LAYRS_AI_TUTOR_REVERSE_ENGINEERING.md`, tutor route and API, migration `20260911_0019_tutor_sessions.py` | Preserve row and evidence link. |
| RE-021 Real-SWE Premium | PR Review Lab | `apps/web/app/pr-review/page.tsx`, PR review routes/domain, migration `20260914_0020_pr_review_sessions.py` | Preserve row and evidence link. |
| RE-022 ClankerRank | AI Arena | `apps/web/app/ai-arena/page.tsx`, `apps/api/src/rigor_api/ai_arena_routes.py`, migration `20260918_0021_ai_arena.py` | Preserve row and evidence link. |
| RE-023 Rigor | Canonical platform | Root `README.md`, `IMPLEMENTATION_PROGRESS.md`, API, web, database, and execution services | Preserve row and evidence link. |

## Identifier collisions

| Legacy repository label | Canonical row that owns the ID | Repository capability evidenced | Correct handling |
| --- | --- | --- | --- |
| RE-292 | DustByte | Code Typing / Codestroke-inspired clean-room transcription (`/practice/code-typing`; PRs #42/#43) | Do not alter DustByte. Keep RE-292 only as historical alias/provenance. Create a separate row with a tracker-allocated free ID. |
| RE-326 | Sky Reach | Falling Words / Typing Arcade (`/practice/typing-arcade`, original deterministic engine; PR #45) | Do not alter Sky Reach. Keep RE-326 only as historical alias/provenance. Create a separate row with a tracker-allocated free ID. |

No free canonical ID is asserted here. The canonical tracker is not present in this checkout and no tracker connector or write credential is available, so collision-free allocation and edits to the external tracker remain pending. Repository issue/PR labels are historical provenance; they are not proof that the same ID belongs to this product in the canonical tracker.

## Candidate capability rows to add after ID allocation

| Proposed row | Why it qualifies | Repository state | Release state |
| --- | --- | --- | --- |
| Mookti-inspired Study Workspace | Distinct outcomes, task planning, study log, focus evidence, flashcards, and spaced review capability | Route `/study-workspace`; local state is account-keyed in browser storage; no API or migration | Implemented locally. Keep behind an explicit feature boundary until the public content license policy, ownership/storage behavior, browser accessibility, and exact-head CI are reviewed. |
| Code Typing | Distinct language-specific transcription practice with its own scoring and history contract | Route `/practice/code-typing`; Python, SQL, JavaScript; local history; no code execution/API | Implemented as bounded guest practice. First-party snippets have no donor source/assets. Public content redistribution license remains unresolved. |
| Typing Arcade / Falling Words | Distinct deterministic game and keyboard practice, not the Sky Reach/Gravitype capability | Route `/practice/typing-arcade`; local device history/settings; no API | Browser vertical slice is implemented in this branch. Real-browser, keyboard/mobile, accessibility and exact-head CI certification remain outstanding. |

## Consolidated capabilities that do not need separate product rows

KeetKote/company interview readiness is part of the Rigor company-preparation capability; DataForge is part of Rigor's Data Engineering preparation. Neither should become a parallel product or runtime simply because its requirements remain separately auditable. Keep their evidence in the capability matrix and the existing Rigor row unless the canonical tracker explicitly models requirement-level subrows.

Explicitly excluded work remains excluded: ApplyAI/CareerOS, StorySprout/Sproutlands, SafeSpark, Number Ninja, InterviewForge AI/Hack2Hire, LeetQuiz, CertForge, Snowflake Brain, Claude Certification Guide, and the Kinduru-inspired flow.

## External reconciliation still required

- Read the canonical tracker and confirm all existing IDs before allocating new ones.
- Allocate unique IDs to Study Workspace, Code Typing, and Typing Arcade if the tracker accepts these as rows.
- Preserve the legacy RE-292 → Codestroke and RE-326 → Gravitype repository aliases as provenance, without changing DustByte or Sky Reach.
- Update the open PR/issue labels and links after the external row mappings are confirmed.
- Do not mark tracker rows complete until the release SHA and tests are recorded in the tracker.
