# Trace Lab delivery roadmap

This roadmap converts the Reify donor findings into an owned SkillForge capability without creating a duplicate product or weakening the existing execution security model.

## Ownership

- Product boundary: SkillForge/Rigor (`rrahul0904/leetcode-platform`)
- Donor: `JanaSundar/reify` pinned at `f31dc691a5d3228ccf2c659f02d55e2d0d41466d`
- REA role: evidence/capability extraction and clean-room constraints
- SkillForge role: owned product/runtime contracts, implementation, tests and release gates

## Workstreams

| ID | Workstream | Owner boundary | Dependency | Acceptance evidence |
| --- | --- | --- | --- | --- |
| TL-01 | Provenance + licensing | REA docs | none | pinned source, MIT/source + branding exception recorded |
| TL-02 | Trace protocol | web/lib + API contract | TL-01 | versioned bounded contract; deterministic replay tests |
| TL-03 | Replay UI | web/components | TL-02 | timeline, variables, stack, output; rewind without rerun |
| TL-04 | Coding-pad integration | existing practice UI | TL-02/03 | trace appears only on provider-returned evidence |
| TL-05 | Python capture provider | isolated execution plane | TL-02 | line/call/return/exception/locals with hard budgets |
| TL-06 | Differential correctness | runner tests | TL-05 | traced vs untraced corpus has identical output/error semantics |
| TL-07 | Persistence/receipts | attempts/progress | TL-05 | bounded trace artifact linked to execution/attempt provenance |
| TL-08 | Tutor grounding | AI tutor | TL-05/07 | tutor can cite exact trace step IDs; cannot invent absent steps |
| TL-09 | Structure visualization | replay UI | TL-05 | arrays/objects first; inferred tree/list only when unambiguous |
| TL-10 | Complexity lab | benchmark worker | TL-05 | static estimate separated from measured fit; reproducible samples |
| TL-11 | JS/TS adapter | isolated runner | TL-02/06 | source maps, approved sandbox, same trace protocol |
| TL-12 | SQL visualization | SQL runtime | TL-02 | query plan/data-flow view; no misleading line-by-line execution |
| TL-13 | Trace comparison | learning layer | TL-07/09 | compare candidate/reference or two attempts by stable step evidence |
| TL-14 | Release hardening | Shipping gate | all required | exact-head CI/security/perf/browser receipts; explicit approval to deploy |

## Current slice on `rea/reify-trace-lab`

Implemented:

- [x] TL-01 provenance/licensing/branding capture
- [x] TL-02 language-neutral trace model and browser-boundary budgets
- [x] TL-02 deterministic replay reducer with rewind tests
- [x] TL-03 first Trace Lab timeline/variables/call-stack/output inspector
- [x] TL-04 optional coding-pad Trace tab driven only by returned trace evidence
- [x] UI/reducer unit tests for the first slice

Not implemented / intentionally blocked:

- [ ] arbitrary user-code trace capture
- [ ] production Python instrumentation
- [ ] persistent trace storage
- [ ] AI-tutor trace grounding
- [ ] complexity benchmark pipeline
- [ ] JS/TS runtime adapter
- [ ] SQL plan visualizer
- [ ] deployment

## Python provider design

The first production provider should be Python because Python is already a first-class SkillForge runtime.

Provider input:

```text
execution_id
question_version_id
source_code
public/custom test input
trace policy + budgets
```

Provider output:

```text
normal judge result
+ optional ExecutionTrace v1
+ trace receipt (provider/runtime/policy/version/truncated/bytes/events)
```

Minimum capture events:

- line
- call
- return
- exception
- binding changes at a supported boundary
- stdout/stderr chunks

The provider must enforce budgets before serialization:

- wall-clock timeout
- max events
- max call depth
- max encoded value size
- max bindings/event
- max object/collection preview size
- max total trace bytes

Values must use shallow, bounded encoding. Secrets and platform environment values must never be included.

## Correctness benchmark corpus

Differential tests are required before production enablement. Each program runs with tracing disabled and enabled; observable behavior must match.

Corpus categories:

- loops and nested loops
- recursion
- closures/nested functions
- exceptions
- list/dict/set mutation
- class/object mutation where supported
- early return/break/continue
- stdout/stderr
- timeout/infinite-loop fixtures
- larger collections at budget boundaries
- representative SkillForge DSA and data-engineering Python problems

For every fixture compare:

- return value or judge output
- exception category/message policy
- stdout/stderr
- public-test pass/fail
- timeout/cancellation behavior

A trace mismatch may fail visualization; it must never silently change the judged program result.

## Product benchmark

The owned feature should beat the donor pattern on integration and trust, not merely reproduce its UI.

Benchmark dimensions:

1. **Truthfulness** — visual state is always backed by execution evidence.
2. **Rewind** — arbitrary step navigation never reruns code.
3. **Debug usefulness** — changed variables and relevant frames are obvious.
4. **Safety** — untrusted code stays in the approved isolated execution plane.
5. **Learning integration** — traces attach to problems, attempts, tutor explanations and review history.
6. **Language fit** — Python first; JS/TS later; SQL gets semantically appropriate plan/data-flow views.
7. **Boundedness** — trace production and replay have explicit resource ceilings.
8. **Provenance** — source/runtime/policy/execution IDs are retained for every persisted trace.

## Release gates

Do not merge/deploy solely because the UI works. Production eligibility requires:

- exact-head web unit tests, lint, typecheck and build
- execution-provider unit/integration tests
- differential correctness suite
- timeout/cancel/budget adversarial tests
- authorization and trace-access checks
- trace payload size/performance benchmarks
- browser replay smoke tests
- no secrets/environment leakage fixtures
- compatibility with current production reconstruction work
- explicit shipping approval under the normal platform gate
