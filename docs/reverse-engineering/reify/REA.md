# REA donor analysis: Reify

Status: active donor/reference
Captured: 2026-10-16
Canonical owner: `rrahul0904/leetcode-platform`
Branch: `rea/reify-trace-lab`

## Source identity

- Reddit source: `https://www.reddit.com/r/coolgithubprojects/comments/1x7ghr8/watching_my_code_actually_run_finally_clicked_for/`
- Product: `https://tryreify.vercel.app/`
- Public repository: `https://github.com/JanaSundar/reify`
- Evidence pin: `f31dc691a5d3228ccf2c659f02d55e2d0d41466d`
- Source license: MIT for source code.
- Branding exception: the upstream README explicitly excludes the Reify name/logo from the software license. No upstream branding is to be reused.

## Routing decision

Reify is a donor/reference, not a new owned standalone product. Its useful product and architecture patterns belong inside the existing SkillForge/Rigor learning and coding-practice product boundary.

Owned feature name: **Trace Lab / Execution Replay**.

No new GitHub repository should be created for this donor.

## Observed capabilities

1. Run real JavaScript/TypeScript and derive visualization from execution rather than a canned animation.
2. Step forward and backward over a recorded execution timeline without rerunning the program.
3. Inspect values, variables, call stack, scope and heap-like object state.
4. Visualize arrays, objects, Maps and Sets, with inferred structures only when shape is unambiguous.
5. Execute tests against user functions and expose pass/fail behavior.
6. Estimate complexity statically and compare it with measured runtime curves.
7. Keep compilation/instrumentation separate from runtime execution.
8. Apply budgets for events, steps and call depth, plus a wall-clock timeout.
9. Use per-run workers and terminate on cancellation/timeout.
10. Preserve source locations so visual steps can map back to code.

## Upstream architecture pattern

Observed high-level flow:

`editor -> execution state machine -> coordinator -> compiler/instrumentation -> fresh runtime -> bounded trace store -> timeline/inspectors`

Important design principle: replay is based on recorded events/snapshots. Moving backward or forward through history should not re-execute candidate code.

## Security finding

Do **not** transplant the upstream browser-worker runtime as our production security boundary. Upstream documentation correctly notes that a Web Worker is not a strong sandbox and cannot guarantee memory limits or fully prevent access to browser capabilities/intrinsics.

SkillForge already has a stronger fail-closed execution posture. Therefore the owned architecture must keep arbitrary candidate execution behind the governed execution plane and treat trace production as an execution-provider capability.

## Clean-room owned architecture

```text
InteractiveCodingPad / Practice Workspace
        |
        v
Trace Lab UI
  - timeline
  - source step marker
  - variables/scope
  - call stack
  - heap/collections
        |
        v
ExecutionTrace protocol (owned, language-neutral)
        |
        +--> replay reducer (browser; pure/deterministic)
        |
        +<-- bounded trace events
                |
                v
Governed execution provider
  - Python runner first
  - future JS/TS runner
  - SQL gets plan/data-flow visualization, not fake line-by-line semantics
```

### Separation of concerns

- **Capture** happens inside an approved runtime provider.
- **Transport** uses a bounded, versioned trace envelope.
- **Replay** is deterministic and pure in the web app.
- **Visualization** consumes replay state and cannot execute code.
- **Persistence** is opt-in and stores bounded trace artifacts, never secrets.

## Initial trace contract

The first owned contract should support:

- monotonic sequence number
- event kind (`line`, `call`, `return`, `assign`, `write`, `output`, `exception`)
- source location
- frame identity
- shallow encoded values
- changed bindings
- call-stack snapshot/reference
- bounded collection/object references
- optional stdout/stderr fragments
- terminal outcome
- truncation metadata when a budget is reached

Hard limits belong in the contract, not only in the UI.

## Language roadmap

### Phase 1: product/UI contract

- language-neutral trace types
- deterministic replay reducer
- timeline/variable/call-stack UI
- fixture-driven tests
- integrate as an optional panel in the existing coding pad

### Phase 2: Python tracing

- instrument approved Python practice execution in the existing isolated runner
- capture line/call/return/exception events and shallow locals
- enforce event/value/depth/bytes/time budgets
- differential tests: tracing must not change normal answer/output/error semantics

### Phase 3: JavaScript/TypeScript

- add JS/TS only through an approved isolated runtime provider
- preserve source maps and language-adapter boundary
- do not use the browser worker as the sole security boundary for untrusted public execution

### Phase 4: richer visualization

- arrays/objects/maps/sets
- linked-list/tree inference only when unambiguous
- complexity explanation and measured benchmarking
- trace comparison between two solutions
- AI tutor references exact trace steps instead of inventing runtime behavior

## Differentiation for SkillForge

The goal is not to clone Reify. The owned advantage is to connect execution replay with the rest of the learning system:

- question-bank problem context and hidden/public tests
- Python/data-engineering tracks, not only JS/TS DSA
- AI tutor grounded in verified trace events
- compare candidate vs reference execution
- generate debugging drills from failed traces
- interview-review receipts showing where reasoning diverged
- replay artifacts linked to attempts/progress
- policy/provenance/verification gates already present in the platform

## Non-goals

- no Reify name/logo or lookalike branding
- no code copy/transplant from upstream unless separately reviewed and attributed under its license
- no claim that a Web Worker makes arbitrary code production-safe
- no fake visualization generated by an LLM when execution evidence is absent
- no production enablement until security, correctness, budget and differential-test gates pass

## REA acceptance gates

A feature may move from donor analysis to implementation only when all of the following are true:

1. source and commit provenance are pinned;
2. licensing/branding constraints are recorded;
3. clean-room owned interfaces are defined;
4. arbitrary-code execution remains fail-closed by default;
5. trace limits are explicit and testable;
6. replay is deterministic from the trace artifact alone;
7. unsupported constructs fail honestly rather than showing misleading state;
8. traced and untraced execution are behaviorally equivalent for the supported corpus;
9. CI/typecheck/lint/tests pass at the exact PR head;
10. no merge/deploy occurs without the normal release gate.
