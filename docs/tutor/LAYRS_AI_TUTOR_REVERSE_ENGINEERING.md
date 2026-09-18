# Layrs AI Tutor reverse engineering -> SkillForge tutor architecture

Status: active implementation
Branch: `agent/layrs-ai-tutor`

This document records only behavior observable from Layrs public product pages and clearly labels architecture that is inferred. The implementation reproduces product patterns, not proprietary source code, prompts, curriculum text, branding, or private APIs.

## 1. Publicly observable product contract

As of 2026-09-11, Layrs publicly describes a tutor with these product behaviors:

- a universal session entry point that can create a lesson, roadmap, or mock session from a free-form learning goal;
- DSA practice in which the tutor sees the coding workspace, observes code/test state, and gives hints rather than immediately revealing answers;
- system-design practice in which the tutor observes a whiteboard, asks trade-off questions, and follows up on weak points;
- realistic mock interviews in which the tutor stays quiet while the candidate works and then challenges decisions;
- role-adaptive system-design curricula from junior through manager, with progressively less teaching and more independent design practice;
- persistent roadmaps, notes, whiteboards, and a concept-mastery graph;
- voice as a separately metered resource, while some text tutoring remains unmetered.

Public references used during discovery:

- https://layrs.me/home
- https://layrs.me/interviews
- https://layrs.me/progress
- https://layrs.me/library
- https://layrs.me/library/dsa
- https://layrs.me/library/system-design-interviews
- https://layrs.me/library/ai-system-design
- https://layrs.me/library/stanford-llm-engineering
- https://layrs.me/pricing

## 2. Core interaction loop

The highest-value behavior is not chat. It is a closed observation/decision/coaching loop:

```text
candidate action
  -> workspace event
  -> safe context projection
  -> intervention policy
  -> tutor reasoning
  -> text/voice response or deliberate silence
  -> candidate action
  -> evaluator/mastery update
  -> next context projection
```

For SkillForge the workspace event may be:

- editor change;
- Run/Submit result;
- explicit hint request;
- long idle period;
- whiteboard node/edge mutation;
- spoken/text candidate explanation;
- timer milestone;
- rubric checkpoint.

The important implementation choice is to send structured state rather than screenshots whenever we own the surface. Code should be represented as code + language + public execution evidence. Whiteboards should be represented as nodes, edges, labels, requirements, and notes. This is cheaper, more reliable, more accessible, and easier to protect than continuous vision capture.

## 3. Inferred end-to-end architecture

The following is an engineering inference, not a claim about Layrs internals.

```text
Browser
  Editor / Whiteboard / Chat / Voice controls
        |
        +--> Workspace Event Bus
        |      code_changed
        |      public_run_completed
        |      whiteboard_changed
        |      help_requested
        |      speech_started/stopped
        |
        +--> Context Projector
        |      allow-listed candidate-visible state only
        |      NEVER hidden tests / reference answers
        |
        +--> Realtime Session Client
               WebRTC/WebSocket for audio + low-latency events
                         |
API / Tutor Control Plane
  Auth + entitlement + quota
  Session state machine
  Intervention policy
  Context compaction / session summaries
  Tool authorization
  Prompt/instruction assembly
  Provider routing
        |
        +--> realtime voice model OR STT -> LLM -> TTS pipeline
        +--> execution/status tool (public result projection only)
        +--> competency/mastery service
        +--> curriculum/roadmap service
        +--> rubric evaluator
        +--> durable session/event store
```

## 4. Tutor state machine

A useful realtime state machine is:

```text
IDLE
 -> LISTENING
 -> THINKING
 -> SPEAKING
 -> LISTENING

Any active state -> INTERRUPTED -> LISTENING
Any state -> ENDED
```

A second orthogonal coaching state controls whether the tutor may speak:

```text
OBSERVE
SILENT
CONCEPT_CHECK
NUDGE
HINT
COMPLEXITY_CHALLENGE
TRADEOFF_CHALLENGE
```

Separating realtime transport state from teaching policy is important. A model should not be able to decide by itself that it is always useful to interrupt.

## 5. Mode policies

### Lesson

Goal: teach a concept interactively.

- explanation chunks should be short;
- periodically ask the learner to restate or apply the concept;
- branch into prerequisite explanations when needed;
- return to the original objective;
- update mastery from demonstrated evidence, not from message count.

### Roadmap

Goal: maintain a multi-session learning plan.

- start from target role/topic, current level, timeline, and prior mastery;
- select competencies rather than a static ordered playlist;
- re-plan after assessment evidence;
- preserve a stable high-level goal while changing individual exercises.

### Practice

Goal: candidate does the work; tutor removes blockers without solving it.

- observe first;
- intervene after repeated public failures, explicit help request, or sustained stall;
- use progressive hints;
- after a passing solution, probe complexity, edge cases, alternatives, and communication;
- for architecture work, probe trade-offs only after enough of the design exists to discuss.

### Mock

Goal: simulate an interviewer, not an assistant.

- stay silent during productive work;
- do not leak solution direction simply because the candidate pauses briefly;
- ask realistic follow-ups;
- use a separate scoring/evaluation pass after the interview;
- retain evidence supporting each rubric score.

## 6. Level adaptation

Public Layrs curriculum pages expose a useful teaching/practice progression. SkillForge's initial policy mirrors the product idea, while leaving exact curriculum content original:

| Level | Learn | Practice | Tutor posture |
| --- | ---: | ---: | --- |
| Junior | 65% | 35% | teach foundations, frequent checks |
| Mid | 50% | 50% | balanced teaching and application |
| Senior | 30% | 70% | challenge assumptions and trade-offs |
| Staff | 15% | 85% | sparse guidance, architecture pressure |
| Manager | 20% | 80% | delivery, risk, trade-offs, execution |

The percentages are configuration, not the intelligence. The durable advantage comes from combining them with SkillForge competency evidence and job-specific gaps.

## 7. Security boundary: tutor-visible != evaluator-visible

SkillForge already has hidden execution evidence and governed solution material. The tutor must not become a side channel around those controls.

Never send to a tutor provider:

- hidden tests or hidden fixtures;
- hidden expected outputs;
- canonical/reference solutions;
- interviewer-only notes;
- answer keys;
- private evaluation traces that reveal hidden cases.

The provider receives an allow-listed projection such as:

```json
{
  "language": "python",
  "source": "candidate-owned source",
  "public_tests_passed": 2,
  "public_tests_total": 4,
  "last_run_status": "failed",
  "public_error_summary": "AssertionError on public case 3"
}
```

`rigor_api.tutor_domain.assert_tutor_context_is_public` exists as a fail-closed guard for raw context assembly, and Pydantic tutor models reject extra fields.

## 8. Event model

Planned durable events:

- `tutor.session_started`
- `tutor.mode_changed`
- `tutor.context_observed`
- `tutor.user_text`
- `tutor.user_voice_segment`
- `tutor.code_changed`
- `tutor.public_run_observed`
- `tutor.whiteboard_changed`
- `tutor.help_requested`
- `tutor.intervention_decided`
- `tutor.response_started`
- `tutor.response_interrupted`
- `tutor.response_completed`
- `tutor.rubric_evaluated`
- `tutor.mastery_delta_recorded`
- `tutor.session_summarized`
- `tutor.session_ended`

The durable event log allows later reconstruction of why a hint, score, or mastery update occurred.

## 9. Voice architecture

Do not put the long-lived provider API secret in the browser.

Planned flow:

1. authenticated SkillForge client requests a short-lived realtime session;
2. API checks plan/quota, candidate ownership, and active tutor session;
3. API returns an ephemeral provider credential or establishes a server relay;
4. browser streams audio over WebRTC where supported;
5. structured workspace events flow separately and are merged into the tutor context;
6. turn summaries are persisted server-side;
7. quota accounting uses actual provider/session duration, not client-reported duration.

Voice should be a transport. The tutor domain/session model must work identically with text-only chat.

## 10. Prompt/orchestration layers

Avoid one giant prompt. Compose policy from independent layers:

1. platform safety and data-boundary policy;
2. tutor identity/style policy;
3. mode policy (lesson/practice/mock/roadmap);
4. seniority/role policy;
5. problem/curriculum context;
6. current safe workspace snapshot;
7. recent summarized interaction state;
8. explicit authorized tools.

For mocks, scoring should be produced by a separate evaluator contract after the conversation rather than by trusting the conversational response to grade itself.

## 11. Mastery model

Mastery should be evidence-based. Candidate evidence may include:

- solved without hints;
- solved after N hint levels;
- correct complexity analysis;
- repeated failure pattern;
- architecture rubric evidence;
- explanation quality;
- spaced-recall success;
- mock-interview rubric scores.

A single successful message must not mark a competency mastered.

## 12. Cost controls

Public pricing strongly indicates realtime voice is the expensive unit. SkillForge should therefore meter provider-intensive voice separately from low-cost text/session persistence.

Controls:

- voice minute quota and top-ups;
- VAD to avoid billing silence where provider semantics permit;
- compact structured context rather than repeated screenshots;
- turn/session summaries instead of replaying full transcripts indefinitely;
- cheaper model for event classification and summarization;
- stronger model only for high-value coaching/evaluation turns;
- provider routing behind a stable internal interface.

## 13. SkillForge implementation waves

### Wave 0 - foundation (in progress)

- safe tutor context contract;
- seniority teaching mix;
- deterministic intervention policy;
- hidden-evaluation leakage guard;
- unit tests.

### Wave 1 - durable text tutor

- tutor session/event schema + RLS;
- candidate-owned session API;
- text turns and streaming responses;
- context projector for current coding workspace;
- progressive hint ladder;
- session summary.

### Wave 2 - coding awareness

- editor event bridge;
- observe public Run/Submit evidence;
- intervention triggers;
- complexity/edge-case probes;
- no-answer-leak contract tests;
- tutor dock inside coding workspace.

### Wave 3 - system-design whiteboard

- first-party structured whiteboard model;
- autosave/versioning;
- tutor context projection from graph state;
- trade-off probes;
- requirements/HLD/deep-dive/trade-off rubric evidence.

### Wave 4 - realtime voice

- ephemeral realtime session endpoint;
- WebRTC audio client;
- interruption/barge-in;
- transcript + session summary persistence;
- authoritative quota accounting;
- text fallback.

### Wave 5 - mastery + roadmap

- evidence-to-competency mapper;
- mastery updates with provenance;
- adaptive next-step selection;
- role/job-driven roadmaps;
- spaced review.

### Wave 6 - mock interviewer

- timed interview state machine;
- deliberate silence policy;
- dynamic follow-ups;
- post-session evaluator;
- rubric evidence and playback/review.

## 14. Definition of done

The tutor is not complete merely because a voice model can talk.

A candidate must be able to:

1. open an existing SkillForge question;
2. start a tutor session;
3. code while the tutor observes only candidate-visible state;
4. run public tests through the existing execution plane;
5. receive a progressive hint after a genuine stall/failure;
6. pass tests and receive a complexity/edge-case challenge;
7. switch to a mock in which the tutor stays silent while they work;
8. resume the session after refresh;
9. see evidence-backed mastery/progress changes;
10. use the same session model through text or realtime voice;
11. prove through tests that hidden tests and reference solutions never enter provider context.
