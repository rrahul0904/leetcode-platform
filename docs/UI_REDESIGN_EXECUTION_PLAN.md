# Rigor Cinematic UI Redesign — End-to-End Codex Prompt

## Mission

Redesign the Rigor Platform Web experience to reach the visual quality, pacing, clarity, and motion polish demonstrated in the supplied screen recording while preserving Rigor's own identity, domain model, navigation, accessibility, and production behavior.

Do not copy the source site's name, text, branding, illustrations, proprietary assets, or exact color palette. Reproduce only the transferable interaction principles:

- restrained dark editorial composition;
- premium serif display hierarchy paired with compact sans/monospace metadata;
- quiet, warm surfaces with thin borders and deliberate negative space;
- strong exam/workspace hierarchy;
- precise hover, focus, loading, transition, and progress feedback;
- motion that communicates state without distracting from practice;
- dense information presented calmly;
- responsive layouts that retain desktop quality on tablet and mobile.

Use Rigor's distinct palette:

- deep graphite/black foundation;
- electric indigo as the primary accent;
- cool mint for success, active, and connected states;
- restrained rose for failure/error states;
- neutral lavender-gray copy and borders.

## Non-negotiable constraints

1. Preserve all current APIs, authentication, routes, execution behavior, persistence, idempotency, and accessibility semantics.
2. Do not replace real functionality with mock data.
3. Do not remove loading, error, empty, retry, cancellation, autosave, or recovery states.
4. Candidate code must continue to execute only through the isolated asynchronous execution plane.
5. Do not add heavy animation or UI libraries unless the existing stack cannot provide the interaction safely.
6. Prefer CSS transitions/keyframes and existing React primitives.
7. Respect `prefers-reduced-motion`.
8. Maintain visible keyboard focus and WCAG AA contrast for body text and controls.
9. Do not claim completion until Web lint, typecheck, tests, and production build pass.
10. Every phase must leave the branch usable.

## Phase 0 — Audit and visual inventory

Inspect:

- `apps/web/app/**`
- `apps/web/components/**`
- `apps/web/lib/**`
- `packages/design-tokens/**`
- current screenshots/tests
- all shared CSS classes in `apps/web/app/globals.css`

Create a compact audit mapping:

- shell/navigation;
- home/dashboard;
- question catalog;
- question detail;
- practice workspace;
- learning paths;
- mock interviews;
- progress/readiness;
- onboarding/auth;
- admin surfaces;
- loading/error/empty states;
- mobile behavior.

Do not redesign before identifying shared patterns and route ownership.

## Phase 1 — Visual foundation

Implement a coherent token layer for:

- background and panel colors;
- text hierarchy;
- accent/success/error colors;
- spacing scale;
- border opacity;
- radius policy;
- elevation/shadows;
- serif/sans/monospace roles;
- transition durations and easing;
- focus rings;
- reduced-motion behavior.

The design should feel editorial and technical, not like a generic SaaS dashboard.

Acceptance:

- no hard-to-read gray-on-black text;
- no inconsistent card radii or shadows;
- no arbitrary per-page accent colors;
- all interactive states are visible with mouse and keyboard.

## Phase 2 — Application shell

Rework the candidate shell into a refined horizontal navigation system:

- compact Rigor identity;
- clear active route indicator;
- low-noise connected/API state;
- premium profile menu;
- responsive full-screen mobile navigation;
- sticky/translucent navigation with subtle blur;
- no layout shift when menus open;
- graceful long labels and smaller laptop widths.

Keep administrator role navigation functional and legible.

Acceptance:

- active route remains obvious;
- desktop navigation does not collide with status/profile controls;
- mobile navigation is keyboard accessible;
- focus returns correctly after closing menus where supported.

## Phase 3 — Home/dashboard

Build a high-quality landing/dashboard experience with:

- oversized serif hero statement;
- Rigor-specific product positioning;
- animated but non-distracting capability visualization;
- primary and secondary calls to action;
- evidence/stat strip;
- four principal practice domains;
- recently published questions;
- personalized target-role context;
- premium loading/error/empty states.

Motion:

- subtle page entrance;
- slow capability-orb movement;
- staggered cards;
- controlled hover elevation;
- no looping animation that competes with reading.

## Phase 4 — Practice workspace

This is the highest-priority product surface.

Upgrade it to an exam-grade technical workspace:

- persistent header with leave action, question identity, timer, autosave/execution state;
- strong problem hierarchy using editorial typography;
- calm instruction/constraint/example blocks;
- high-contrast code editor surface;
- clear Run, Submit, and Cancel hierarchy;
- animated queued/running/completed/failed states;
- readable public-test results;
- visible but restrained deterministic evaluation summary;
- preserved local execution recovery and autosave behavior;
- desktop split layout;
- tablet/mobile stacked layout without lost controls.

Do not turn the coding workspace into a multiple-choice exam clone. Translate the recording's hierarchy and quality into Rigor's real coding workflow.

Acceptance:

- source code remains responsive during polling;
- results do not cause disruptive layout jumps;
- timer uses tabular numerals;
- status is understandable without relying on color alone;
- hidden answers remain absent from candidate-visible state.

## Phase 5 — Catalog and question detail

Apply the system to:

- question-bank cards;
- filters and search;
- pagination;
- external references;
- question detail reading layout;
- metadata tags;
- start/continue practice actions.

Use article-like reading widths and a disciplined card grid. Avoid dense generic tables for candidate-facing content.

## Phase 6 — Learning, mock, progress, and onboarding

Create consistent premium surfaces for:

- preparation paths;
- mock interview configuration;
- readiness evidence;
- progress history;
- onboarding and profile editing;
- authentication/session restoration.

Use motion to communicate progression and state transitions, not decoration.

## Phase 7 — Admin compatibility

Ensure the new foundation does not reduce operational clarity for:

- content management;
- review queues;
- source governance;
- catalog status;
- forms and data tables.

Admin surfaces may remain denser, but they must inherit the same typography, focus, border, color, and feedback system.

## Phase 8 — Validation

Run and report:

```bash
pnpm --filter @rigor/web lint
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web test
pnpm --filter @rigor/web build
```

Also validate:

- 1440px desktop;
- 1024px tablet landscape;
- 768px tablet portrait;
- 390px mobile;
- keyboard navigation;
- reduced motion;
- long question titles;
- empty and error states;
- slow/failed execution polling;
- active execution recovery after refresh.

## Required completion report

For every phase, report:

- files changed;
- visual/interaction behavior delivered;
- functional behavior preserved;
- responsive/accessibility evidence;
- exact test commands and results;
- remaining gaps.

Use only these status labels:

- IMPLEMENTED
- VALIDATED LOCALLY
- VALIDATED IN CI
- BLOCKED EXTERNALLY
- NOT IMPLEMENTED

Do not describe source code alone as a completed visual experience. A phase is complete only after the production Web build passes and its critical interactions are exercised.
