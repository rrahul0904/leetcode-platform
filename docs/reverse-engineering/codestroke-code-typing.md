# RE-292 — Developer code typing practice: public product research and clean-room contract

**Date:** 2026-09-26  
**Research target:** https://codestroke.dev/test/python  
**Canonical project:** `rrahul0904/leetcode-platform` (distinct learning/practice module, not ApplyAI)  
**Tracking issue:** https://github.com/rrahul0904/leetcode-platform/issues/41  
**State:** Public research and independently designed scope; no feature implementation, E2E certification, or deployment claimed.

## 1. Product interpretation

Codestroke is **typing real code as text**, measuring speed and accuracy for developers who want symbol/indentation familiarity; it does not ask users to solve, execute or debug code. The developer's motivation is declining comfort with manual code entry as AI does more drafting; that personal motivation is not a validated market-size claim. The SQL product page explicitly distinguishes code typing from database execution.

## 2. Source-grounded feature matrix

| Area | Supported public information | Evidence |
|---|---|---|
| Languages | JavaScript, HTML/CSS, Python, SQL, Java, C++, PHP, Go, Kotlin | [Python route](https://codestroke.dev/test/python) |
| Sessions | 30, 60 and 120 seconds; language switch; shuffle | [Python route](https://codestroke.dev/test/python) |
| UI | focus/type to start; live CPM, accuracy and time; copy/paste and drag/drop stated disabled | [Python route](https://codestroke.dev/test/python) |
| Content | Python: comprehensions, decorators, classes/types, async and indentation; SQL: SELECT, JOIN, aggregates, CTE/window patterns | [Python](https://codestroke.dev/test/python), [SQL](https://codestroke.dev/test/sql) |
| Metrics | CPM, WPM (site explains WPM = CPM/5), accuracy, session result/history | [About](https://codestroke.dev/about) |
| Guest & auth | Guest progress/preferences local to browser; optional email/Google account, optional claim/sync | [Privacy](https://codestroke.dev/privacy), [Terms](https://codestroke.dev/terms) |
| Public leaderboard | Signed-in full validated challenges; three validated sessions before eligible best-CPM Top 20 per language/duration | [Leaderboard](https://codestroke.dev/leaderboard) |
| Account privacy | User may clear history/delete account; leaderboard projection is removed with underlying data; no payment collection stated | [Privacy](https://codestroke.dev/privacy) |
| Disclosed providers | Supabase auth/DB, Resend email, Google sign-in/GA4, Vercel hosting/analytics/performance | [Privacy](https://codestroke.dev/privacy) |

The product's disclosures do NOT prove exact framework, table schema, state machine, backend scoring, server validation logic, code structure or private APIs.

## 3. Founder posts and visible feedback

- [SideProject launch post](https://www.reddit.com/r/SideProject/comments/1wqnaoy/ai_made_me_rusty_at_typing_code_so_i_built_a/): a participant suggests levels, with an easy hello-world starting level. The creator says they directed AI-generated development for visual/feature preferences; do not infer their entire codebase or quality from the comment.
- [VibeCodeDevs thread](https://www.reddit.com/r/VibeCodeDevs/comments/1wqop28/vibe_coding_made_me_realize_i_barely_type_code/): a commenter proposes a VS Code plugin.
- [KeyboardLayouts thread](https://www.reddit.com/r/KeyboardLayouts/comments/1wqn3qn/how_does_your_keyboard_layout_handle_typing/): a participant questions line-by-line manual transcription relative to autocomplete/snippet-assisted editing. Keep typing fluency distinct from complete IDE workflow or programming skill.
- [WebApps launch thread](https://www.reddit.com/r/WebApps/comments/1wqn4ua/i_built_codestroke_a_free_typing_test_for_actual/): creator explicitly seeks feedback on multiline/symbol transitions.
- [buildinpublic question](https://www.reddit.com/r/buildinpublic/comments/1wqorz5/im_building_a_code_typing_test_and_im_figuring/): snippet quality, progress and leaderboards are possible retention hypotheses, not proof of shipped behavior.

**Evidence limit:** only comments exposed in accessible pages were reviewed; do not assert invisible replies have been examined or no other discussions exist.

## 4. Clean-room product architecture for our existing learning suite

Keep the module under a separate frontend namespace, e.g. `/practice/code-typing`, with independent `TypingEngine`, `SnippetRenderer`, `SessionResult` and `TypingHistory`. The snippet is static learning content and **must never be routed to the code execution/assessment runner**.

Original, editorially reviewed snippet metadata: stable snippet ID/version, language, topic, difficulty, expected text, normalized newline policy, indentation policy, license/provenance, accessibility text and deprecation state. First vertical slice: original Python, SQL and JavaScript snippets; nine-language support is a later audited content milestone.

Session contract: idle -> active on first accepted input -> completed/timed-out/cancelled; monotonic clock; explicit handling of characters, line breaks, tab behavior, backspace, selection, IME/composition, Unicode, CRLF and long-line display. Preserve deterministic test fixtures. A browser-only paste/drop barrier enforces practice UX but is not sufficient cheating prevention.

Publish **our own** metrics definition before implementation: gross typed characters, correctly aligned characters, correction model, duration, net/gross CPM, WPM = selected CPM / 5 and declared accuracy denominator. No assertion that this is the proprietary upstream formula.

- **A — Guest first:** local, versioned session history and preference storage; explicit clear; simple result/progress view; replay and shuffle.
- **B — Optional account:** owner-isolated synchronization, idempotent result writes, consensual guest import, deletion and migration tests; reuse existing identity infrastructure instead of copying third-party services by name.
- **C — Optional verified challenge:** server-minted challenge ID/nonce/expiry, authenticated completion, immutable snippet version, server recalculation/timing sanity, rate limits, replay/duplicate prevention, privacy-scoped Top 20 projection. Do not call a client-submitted score authoritative.
- **D — Feedback experiments:** beginner-to-advanced levels, symbol/error drill, progress charts, keyboard layout preferences and an IDE integration only after the core proves useful.

## 5. Definition of done

1. Rights-cleared original snippets, no copying target branding, visual design, source, proprietary content or nonpublic endpoints.
2. Unit/property tests: whitespace, quotes/brackets, multiline/tab/CRLF, backspace/error-correction, zero elapsed/timeout/early finish, Unicode/IME, selection, paste/drop and focus.
3. Browser E2E: switch language/duration, shuffle, first-keystroke start, live counters, completion/retry/history/clear, refresh persistence; desktop/mobile, screen-reader reading order, keyboard and reduced motion.
4. Optional B/C security: session ownership/RLS, stale nonce/replay/rate-limit, clock manipulation, fabricated score, injection/XSS and deletion removing public projections.
5. Exact-head tests, CI and real deployed browser screenshots before marking feature complete or hosted-ready.

## 6. Research ethics and outstanding verification

The target's [Terms](https://codestroke.dev/terms) restrict reverse engineering the service and copying its software/design/content. This document therefore records publicly published behavior and an independent design; no source/bundle/API inspection or disruption was performed. A browser-interaction runner was unavailable in this session: first-keystroke correctness, actual results screen, sign-in/profile and real challenge submission have **not** been independently exercised. No upstream private repository or scoring implementation is verified. Record implementation PR/SHA/CI/deployment only after those exist.
