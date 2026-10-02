# Reverse-engineering tracker reconciliation

Audit date: 2026-10-02. Repository release SHA: `8009deec1fa24ced1cb6a00a92e884af24e1ea39` (merged by PR #46 from candidate `9fd7d7e370afd48a9c90e73c133458c7b97a5741`). The canonical tracker remains unavailable in this checkout.

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

## Source PR disposition

PRs #39 (launch assurance), #40 (Study Workspace), #43 (Code Typing implementation), and #45 (Typing Arcade engine) are already merged to `main`; PR #46 integrates their release candidate and exact-main checks. PR #42 remains open and contains documentation-only Codestroke public-behavior research and a clean-room contract, with no application code or deployment claim. Its research file is not in the PR #46 release tree, so it is preserved as historical/provenance material rather than closed as superseded. No source PR was closed during this release audit.

## Candidate capability rows to add after ID allocation

| Proposed row | Why it qualifies | Repository state | Release state |
| --- | --- | --- | --- |
| Mookti-inspired Study Workspace | Distinct outcomes, task planning, study log, focus evidence, flashcards, and spaced review capability | Route `/study-workspace`; local state is account-keyed in browser storage; no API or migration; exact-main-SHA CI passes | Implemented as browser-local functionality. Browser accessibility certification and an external tracker row remain pending. |
| Code Typing | Distinct language-specific transcription practice with its own scoring and history contract | Route `/practice/code-typing`; Python, SQL, JavaScript; local history; no code execution/API; exact-main-SHA CI passes | Implemented as bounded guest practice. First-party snippets have no donor source/assets. Public content redistribution license policy and tracker allocation remain unresolved. |
| Typing Arcade / Falling Words | Distinct deterministic game and keyboard practice, not the Sky Reach/Gravitype capability | Route `/practice/typing-arcade`; local device history/settings; no API; exact-main-SHA CI passes | Implemented. Real-browser, keyboard/mobile, accessibility certification and tracker allocation remain outstanding. |

## Consolidated capabilities that do not need separate product rows

KeetKote/company interview readiness is part of the Rigor company-preparation capability; DataForge is part of Rigor's Data Engineering preparation. Neither should become a parallel product or runtime simply because its requirements remain separately auditable. Keep their evidence in the capability matrix and the existing Rigor row unless the canonical tracker explicitly models requirement-level subrows.

Explicitly excluded work remains excluded: ApplyAI/CareerOS, StorySprout/Sproutlands, SafeSpark, Number Ninja, InterviewForge AI/Hack2Hire, LeetQuiz, CertForge, Snowflake Brain, Claude Certification Guide, and the Kinduru-inspired flow.

## External reconciliation still required

- Read the canonical tracker and confirm all existing IDs before allocating new ones.
- Allocate unique IDs to Study Workspace, Code Typing, and Typing Arcade if the tracker accepts these as rows.
- Preserve the repository's historical Codestroke-inspired label for Code Typing and Gravitype-inspired label for Typing Arcade only as provenance. RE-292 belongs to DustByte and RE-326 belongs to Sky Reach; neither ID maps to these new capabilities.
- Update the open PR/issue labels and links after the external row mappings are confirmed.
- Do not mark tracker rows complete until the release SHA and tests are recorded in the tracker.
