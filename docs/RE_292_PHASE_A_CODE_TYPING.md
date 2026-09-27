# RE-292 Phase A — independent guest code typing

Tracking: issue #41; research-only PR #42. This implementation branch is separate from the research PR.

## Boundary and content

`/practice/code-typing` is a public, client-side text transcription exercise. Only that
route is excepted from the existing authentication gate. No snippet text or entered text
is passed to the API, hostile-code runner, assessment engine, account sync or analytics.
There is no evaluation of code behavior, challenge signature or leaderboard. The
exercise does not attempt to reproduce any third-party layout, source or scoring internals.

The manifest holds six independently authored teaching examples (two each: Python,
SQL and JavaScript). Each has schemaVersion=1, a stable ID, content version, difficulty,
topic, text, 2/4-space indentation, attribution/provenance, rights-status text and
deprecation flag. All six are project-authored for this implementation; **editorial
rights review is still pending** before wider distribution. Change `version` when
changing the expected text; preserve older versions when historical interpretation
matters. Length is computed by Unicode code points rather than hand-maintained.

## Input and state contract

- `idle`: timer has not started; empty/no-op edits do not start it.
- First accepted non-empty text edit transitions to `active` and captures
  `performance.now()`; no wall-clock time is used for scoring.
- `active`: the full textarea value is normalized (CRLF/CR to LF; tabs to the
  snippet's declared number of spaces), with ordinary selection, deletion,
  line-break and correction handling. IME text is committed at composition end.
  Plain Tab in the editor inserts indentation, Shift+Tab retains native navigation.
- Exact normalized equality with expected text transitions to `completed` and
  stops time. An elapsed duration >= 30/60/120 seconds transitions to
  `timed-out` **before** accepting any input at the deadline. A monotonic elapsed
  lower bound prevents a backward clock reading from decreasing duration.
  Hidden/background tabs continue to count; the visibility event catches up on return.
- A reset, shuffle, language or duration change abandons the current session and
  creates a fresh idle session; unfinished abandoned sessions are not stored.
  Pure `cancelSession` is available for explicit terminal cancellation. Completed,
  timed-out and cancelled sessions cannot accept further edits.
- Paste and drag/drop are suppressed for the exercise. This is **not anti-cheat**;
  client-side scores are unverified and must never enter a trusted leaderboard.
  The textarea remains visible as a touch/virtual keyboard fallback. No code executes.

## Scoring contract (our definitions; not an upstream formula)

`correctChars` counts currently visible input code points equal to the corresponding
expected code point at the same index, even beyond an earlier wrong character.
`insertedChars` counts new code points in each accepted edit, using common prefix
and suffix to distinguish selected-text replacement and deletion. `correctInsertions`
counts inserted code points correct at their absolute alignment position. Deleted
mistakes remain in those historical counters; backspace itself adds zero. Whitespace,
symbols, line breaks and Unicode scalars count the same as other characters.

- Net CPM = `correctChars * 60 / elapsedSeconds`.
- Gross CPM = `insertedChars * 60 / elapsedSeconds`.
- WPM = net CPM / 5.
- Accuracy (%) = `100 * correctInsertions / insertedChars` (historical, including
  corrected mistakes). With no insertions accuracy is 100%.
- All speeds are 0 at zero elapsed; no NaN/Infinity. Display values are rounded,
  while guest history stores finite unrounded values. Timeouts score the partial
  text, not a fictitious completion. First-input start means an instantaneous
  artificial full-value change also has zero elapsed CPM; browser paste/drop
  suppression is not authority over programmed clients.

## Guest history and privacy

Only terminal completed/timed-out summaries are stored under
`rigor.code-typing.guest-history.v1`: version, random local ID, snippet ID/version,
language, status, duration, elapsed, scoring counters and a wall-clock display
timestamp. It retains up to 30 entries; reads reject corrupt/unversioned items,
and append deduplicates IDs. Input transcription text is never persisted.
`Clear history` deletes the module's own key; it does not touch other app
storage. Storage failures are surfaced and do not block typing.

## Focused verification and honest limits

Run (with repository dependencies installed):

```bash
pnpm --filter @rigor/web exec vitest run lib/code-typing/engine.test.ts components/code-typing-practice.test.tsx
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web lint
```

Unit tests cover deterministic transitions, monotonic time/deadline, zero-time
metrics, corrections, selected replacement, indentation/CRLF/Unicode, manifest and
guest history. React Testing Library + jsdom DOM/browser-simulation tests cover
controls, shuffle/restart, keyboard/paste/drop, progression, expiry and refresh/clear.
These are **not evidence of a real-device Playwright run or a deployed preview**.
Before broader release, conduct real desktop/mobile browser and accessibility
testing, editorial rights review and exact-head CI/preview verification. This slice
is not an upstream parity or production launch claim.
