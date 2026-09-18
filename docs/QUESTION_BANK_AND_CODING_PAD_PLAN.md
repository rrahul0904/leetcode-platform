# Question Bank and Interactive Coding Pad Milestone

## Objective

Freeze unrelated product expansion and make two candidate journeys dependable:

1. discover the right question from a large, maintainable bank;
2. solve Python and SQL questions in a real interactive workspace.

## Release gates

### Question bank

- Import and verify at least 3,425 canonical searchable records.
- Keep canonical problem, company observation, topic, statement, solution, and source provenance separate.
- Expose explicit candidate statuses: `runnable`, `hosted`, `reference_only`, and `in_review`.
- Support server-side search, company, topic, difficulty, language, status, and frequency filters.
- Preserve filters in the URL and paginate deterministically.
- Deduplicate canonical slugs and company observations during import.
- Show full statements only when present; never invent missing problem text.
- Keep imported solutions unavailable until technical validation and publication.
- Add bank-health verification to CI and clean Docker bootstrap.

### Interactive coding pad

- Provide Python 3.13 and PostgreSQL 18 modes.
- Show line numbers, tab indentation, bracket-aware editing, and keyboard shortcuts.
- Autosave drafts per question and language and recover after refresh.
- Support custom test input, Run, Submit, reset, and output/result tabs.
- Keep the editor responsive while asynchronous execution is queued.
- Display queue, running, completed, failed, timed-out, and cancelled states.
- Render public-test failures without exposing hidden-test data.
- Provide SQL schema and result-grid panels for SQL questions.
- Remain usable with keyboard-only navigation and narrow screens.

## Delivery sequence

1. Source-backed bank import and integrity checks.
2. Candidate status model and filters.
3. Reusable coding-pad shell.
4. Python execution integration.
5. SQL schema/result integration.
6. Convert statement-backed imports into validated runnable packages.
7. Browser E2E, accessibility, resilience, and capacity evidence.

## Definition of done

A candidate can search thousands of canonical questions, filter to runnable Python or SQL work, open a complete statement, edit with a real coding pad, run public/custom tests, submit to hidden evaluation, refresh without losing work, and review the deterministic result. All required workflows must pass on the exact merge commit.
