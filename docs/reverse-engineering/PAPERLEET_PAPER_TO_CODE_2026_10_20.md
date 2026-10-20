# PaperLeet REA intake — Paper-to-Code Lab (2026-10-20)

## Decision

**DONOR / capability extension** to the existing Rigor/SkillForge repository, not a new clone or independent product. Governance: https://github.com/rrahul0904/agent-work-os/issues/340

## Source evidence

- Reddit discussion: https://www.reddit.com/r/learnmachinelearning/comments/1x9rqda/these_people_be_out_here_trying_to_ruin_another/
- Upstream offline edition: https://github.com/Hongyang-Du/PaperLeet ; inspected main SHA 4f429a6702afd990152530a9003883210908c6f4 (2026-10-19).
- Live site: https://paperleet.com ; published and offline catalog may differ; do not conflate counts.
- README self-reports 49 offline papers, 63 exercises, 491 layered checks and 257 intentional buggy implementations; these numbers are upstream claims, not independently reproduced results.
- Root LICENSE: MIT, PaperLeet contributors 2026; inspect dependency/third-party terms and research-paper assets separately. Do not copy upstream branding, problem prose, lab imagery, or hosted private evaluation data.
- Upstream references: papers.yaml catalog; problems exercises; paperleet/judge local runner; local CPU PyTorch and web workspace.

## Existing Rigor/SkillForge inventory (inspected main 2e785369d97c387932931e1954b1b715183b5784)

- docs/TECHNICAL_LEARNING_CONSOLIDATION.md already identifies canonical identity, publishing, question bank, learning paths, tutor, AI Arena, mock interviews and evidence.
- docs/LOCAL_EXECUTION.md defines durable queue, local Python/SQL runners, public vs hidden tests, restricted execution and production sandbox caveat.
- Content already lives under content/questions with question.json, metadata.json, rights.json, rubric.json, solution.json and public/hidden tests.
- No new user/auth store, AI coach, question judge, credential boundary or standalone learning service should be introduced.

## Proposed owned difference

Original paper-to-code challenges with bibliographic provenance, selected mechanism scope, runnable deterministic mathematical oracles, adversarial mutants, CPU lab artifacts, reviewed rubric, verified user mastery and linkable systems engineering follow-ups. Add applied RAG, ranking, LLM fine-tuning, data quality, inference, agent evaluation and production reliability challenges beyond pure paper reproduction.

## P0 independently authored, testable prototype

Location: research/rea/paper-to-code-pilot/. Stable Boolean-masked attention weight normalization (Python stdlib) references the basic attention mechanism in Vaswani et al., 2017, arXiv:1706.03762. No article prose or figures included. Reference and starter are separately stored; 7 deterministic local tests passed before upload. This is an algorithmic teaching slice, NOT a full Transformer or a general-purpose candidate judge.

## Phased delivery and gates

1. **REA + provenance**: pin upstream evidence, license third-party libraries/assets; make original first-party challenge contracts and source/bibliography traceability.
2. **Governed content**: map pilot to SkillForge question schema and skills; content must pass rights, duplicate, executable, rubric, technical and editorial gates. Never auto-publish.
3. **Paper Lab UX**: paper/version explainer, selected mechanism, code editor, hints, CPU experiment artifacts and scoped comparisons; no unapproved brand copying.
4. **Secure execution**: reuse durable runner/outbox/submission records and server-authoritative evaluation; local Compose is only trusted dev. Production needs gVisor/K8s or equivalent, hard quotas, no network/credentials, adversarial verification.
5. **Progress + tutor**: map proof-backed learning outcomes to published content versions, candidate mastery, mock interviews, tutor Socratic assistance and AI Arena; secret hidden tests never reach LLM prompts.
6. **Delivery**: accessibility, observability, performance, abuse tests, cost constraints, Windows/macOS/Linux browser QA, mobile-responsive UX, explicit release approval.

## Definition of done

- [ ] Verified input/output schemas and independent reference oracles, with deliberate buggy variant detection.
- [ ] Rights/provenance and paper-bibliography/license review of each problem, author and source artifact.
- [ ] Proper reviewer-only solutions/hidden tests and versioned publication states.
- [ ] Model-free offline exercise flows; optional AI tutor failure is explicit and fail-closed.
- [ ] No execution in app/API process; load, hostile input, isolation and quota receipts at production target.
- [ ] Evidence-backed learner progress and published first-party content.
- [ ] Human approval for branch merge, hosted publication and deployment.

## Release claim

The pilot tests confirm local reference behavior only. Integration, production isolation, browser acceptance and publication remain unverified.