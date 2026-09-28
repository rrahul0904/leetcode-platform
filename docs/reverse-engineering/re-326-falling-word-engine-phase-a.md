# RE-326 Phase A: owned falling-word simulation core

**Tracking:** [issue #44](https://github.com/rrahul0904/leetcode-platform/issues/44)
**Scope:** original TypeScript engine and focused Vitest tests only. No borrowed source, assets, dictionaries or upstream branding are included.

## Engine interface

File: apps/web/lib/falling-words/game-engine.ts. It is headless, with no browser, network, disk, React, canvas, terminal or package-install side effects. Callers inject a clock (now(): number) and RNG (random(): number in [0,1)); supplying the same draws, clock readings, calls and deltas reproduces a run. Wall-clock readings timestamp start/finish with backward readings clamped; tick(deltaMs) is the sole source of active simulation elapsed time. Increments must be finite, nonnegative and no larger than 60 seconds per call. Pauses and terminal states ignore ticks.

State graph: menu -> ready -> playing <-> paused, with terminal won, lost, exited. prepare enters ready from menu; restart enters ready from any state and records an in-progress run as exited exactly once; exit records only an in-progress run. Only start from ready creates a new run ID. Terminal results contain reason, score, level, lives, matched/missed counts, simulation duration and timestamps; a finished run is never recorded twice. The getter returns defensive copies.

The initial board is empty. Level-dependent spawn and movement schedules use discrete event ordering; movement precedes spawn at a tie. A spawn draws a board-fitting word from the explicitly supplied editorial pool and then chooses uniformly among available x positions at y=0; a blocked entry row skips that attempt. Each movement takes every active item one row down. Items crossing the lower boundary are removed and cost one life each, clamped at zero. No new events are processed after terminal loss. Resizing a live board is **not implemented**; width and height are immutable per engine instance.

Input is exact, case-sensitive and untrimmed; only a whole displayed label is accepted. Among duplicates, the lowest (greatest y) is removed; a y tie resolves to the oldest ID. Text validation accepts 1–64 printable ASCII characters, including internal phrase spaces and punctuation, but rejects surrounding spaces and control/unicode characters; words wider than the board are filtered and at least one must fit. The scoring contract is **10 points per displayed printable character**, including internal spaces/punctuation. Starting lives default to three. Level is min(winningLevel, 1 + floor(score / pointsPerLevel)); defaults are 150 points per level and level 27 as the terminal win. An in-flight spawn or movement interval is not rescheduled by scoring; subsequent intervals use the new level.

## Focused evidence and boundaries

Command: pnpm --filter @rigor/web test -- lib/falling-words/game-engine.test.ts. Focused tests exercise lifecycle, input guards, controlled ticks, partition invariance, first spawn and collision, exact phrase/case matching, duplicate priority, scoring, level progression/27 threshold, pause, restart, wall clock rollback, RNG validation, snapshot isolation, and one-time terminal results.

The engine is intentionally separate from /practice/code-typing, the proposed future /practice/falling-words browser route, and any independently packaged Textual terminal program. No adapter, authored public dictionary, replay serialization, accessibility UX, browser E2E, persistence, distribution, real install test, deployed preview or upstream parity is claimed here. Existing repository-wide CI remains a distinct exact-head gate; do not infer passing checks from test source or workflow declarations. A future adapter must separately specify input/composition and mobile/reduced-motion behavior and must not treat client-submitted scores as authoritative multiplayer/leaderboard data.
