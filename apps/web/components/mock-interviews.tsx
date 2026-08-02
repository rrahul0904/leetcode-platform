"use client";

import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock3,
  Flag,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Domain = "coding" | "sql" | "architecture" | "leadership";

type ExamQuestion = {
  id: string;
  domain: Domain;
  eyebrow: string;
  title: string;
  scenario: string;
  answers: readonly string[];
};

const domainMeta: Record<Domain, { label: string; accent: string }> = {
  coding: { label: "Coding systems", accent: "coral" },
  sql: { label: "SQL & data", accent: "gold" },
  architecture: { label: "Architecture", accent: "violet" },
  leadership: { label: "Staff leadership", accent: "teal" },
};

const questions = [
  {
    id: "q1",
    domain: "coding",
    eyebrow: "CODING SYSTEMS · QUESTION 1",
    title: "A worker pool becomes progressively slower after traffic spikes. What should you inspect first?",
    scenario:
      "The service recovers after a restart. CPU is moderate, memory keeps rising, and latency increases only after several thousand jobs have completed.",
    answers: [
      "Increase the replica count and leave the process unchanged.",
      "Inspect retained task references, queue ownership, and cleanup paths before scaling.",
      "Disable metrics because instrumentation is likely causing the slowdown.",
      "Increase every timeout so jobs have longer to finish.",
    ],
  },
  {
    id: "q2",
    domain: "coding",
    eyebrow: "CODING SYSTEMS · QUESTION 2",
    title: "Which contract makes an execution retry safe when the first response is lost?",
    scenario:
      "A client submits a job, the server commits it, and the network drops before the response arrives. The client retries the same request.",
    answers: [
      "A random request identifier generated independently for every retry.",
      "An idempotency key with a durable uniqueness boundary and replayed result.",
      "A longer client timeout with no server-side state.",
      "A second queue that receives all duplicate requests.",
    ],
  },
  {
    id: "q3",
    domain: "coding",
    eyebrow: "CODING SYSTEMS · QUESTION 3",
    title: "A public API accepts a dictionary payload. How should a Python runner invoke the published function?",
    scenario:
      "The content contract declares keyword arguments, but the runner currently passes the entire dictionary as one positional value.",
    answers: [
      "Always call the function with one positional dictionary.",
      "Infer the invocation mode from the number of dictionary keys.",
      "Honor the explicit invocation contract and call the function with keyword arguments.",
      "Convert every dictionary to a JSON string before invocation.",
    ],
  },
  {
    id: "q4",
    domain: "sql",
    eyebrow: "SQL & DATA · QUESTION 4",
    title: "A candidate query passes locally but fails against hidden fixtures. What is the most likely contract gap?",
    scenario:
      "The visible database was initialized once. Hidden tests provide their own DDL and seed data, but the runner ignores both fields.",
    answers: [
      "The candidate should be allowed to modify the application database.",
      "Each test should create an isolated ephemeral database and apply its declared fixtures.",
      "Hidden tests should share one mutable database for speed.",
      "The Web application should execute the SQL directly.",
    ],
  },
  {
    id: "q5",
    domain: "sql",
    eyebrow: "SQL & DATA · QUESTION 5",
    title: "Which index best supports a company-filtered problem list ordered by frequency?",
    scenario:
      "The dominant access path filters observations by company and then orders the matching problem rows by descending frequency.",
    answers: [
      "An index on the problem title only.",
      "A composite index beginning with company_id, then frequency, then problem_id.",
      "A hash index on the rendered HTML.",
      "A separate database for every company.",
    ],
  },
  {
    id: "q6",
    domain: "sql",
    eyebrow: "SQL & DATA · QUESTION 6",
    title: "How should candidate notes be isolated in a shared PostgreSQL cluster?",
    scenario:
      "Every candidate uses the same application service, but no candidate may read or update another candidate's private notes.",
    answers: [
      "Filter by candidate ID only in the browser.",
      "Use row-level security tied to transaction-scoped identity, plus application authorization.",
      "Store the candidate ID in a hidden form field.",
      "Grant the application role ownership of every table.",
    ],
  },
  {
    id: "q7",
    domain: "architecture",
    eyebrow: "ARCHITECTURE · QUESTION 7",
    title: "Where should untrusted candidate code execute in a production interview platform?",
    scenario:
      "The platform has Web and API services on Fargate, an application database, and an isolated Kubernetes execution plane.",
    answers: [
      "Inside the Web container so results return quickly.",
      "Inside the API process with a short timeout.",
      "Inside isolated sandbox jobs on dedicated execution nodes with network denial.",
      "Inside the mobile application while it is offline.",
    ],
  },
  {
    id: "q8",
    domain: "architecture",
    eyebrow: "ARCHITECTURE · QUESTION 8",
    title: "What is the correct boundary between submission acceptance and sandbox execution?",
    scenario:
      "The API must acknowledge submissions without waiting for an unpredictable runner lifecycle or losing work during a crash.",
    answers: [
      "Call Kubernetes synchronously from the request thread.",
      "Persist the submission and transactional outbox, then dispatch asynchronously.",
      "Keep the submission only in process memory.",
      "Send candidate source code through the analytics pipeline first.",
    ],
  },
  {
    id: "q9",
    domain: "architecture",
    eyebrow: "ARCHITECTURE · QUESTION 9",
    title: "What evidence proves that a sandbox is using the intended runtime isolation?",
    scenario:
      "The deployment manifest names a RuntimeClass, but production readiness requires proof from a live cluster rather than source inspection alone.",
    answers: [
      "A screenshot of the Terraform module.",
      "A successful local unit test.",
      "A live workload showing the selected RuntimeClass, sandbox runtime, and denied egress.",
      "A README statement that isolation is enabled.",
    ],
  },
  {
    id: "q10",
    domain: "leadership",
    eyebrow: "STAFF LEADERSHIP · QUESTION 10",
    title: "A large delivery is nearly complete, but five security defects remain. What should the technical lead do?",
    scenario:
      "The pull request is mergeable and most tests pass. The defects affect network policy, execution contracts, and fixture isolation.",
    answers: [
      "Merge immediately because the feature count is high.",
      "Document the defects as future work and declare production readiness.",
      "Freeze scope, fix the release-blocking defects, and merge only the exact green head.",
      "Remove the failing tests from CI.",
    ],
  },
  {
    id: "q11",
    domain: "leadership",
    eyebrow: "STAFF LEADERSHIP · QUESTION 11",
    title: "How should a team handle a large external question corpus with uncertain rights?",
    scenario:
      "The files are technically parseable, but several sources have no included license and some material appears derived from paid products.",
    answers: [
      "Publish everything because it was available on GitHub.",
      "Separate provenance from publication, quarantine uncertain material, and require an explicit rights disposition.",
      "Remove source attribution after import.",
      "Treat every repository as public domain.",
    ],
  },
  {
    id: "q12",
    domain: "leadership",
    eyebrow: "STAFF LEADERSHIP · QUESTION 12",
    title: "What makes an interview-preparation product feel credible to senior candidates?",
    scenario:
      "The system has broad content coverage, but users must decide whether to trust its recommendations and invest many hours in it.",
    answers: [
      "Maximize decorative animation and hide limitations.",
      "Use evidence-backed progress, clear states, purposeful workflows, and consistent interaction quality.",
      "Show as many dashboard cards as possible.",
      "Replace all explanations with generated summaries.",
    ],
  },
] as const satisfies readonly ExamQuestion[];

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function MockInterviews() {
  const [stage, setStage] = useState<"intro" | "exam" | "complete">("intro");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [remaining, setRemaining] = useState(45 * 60);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [flagged, setFlagged] = useState<Set<string>>(() => new Set());

  const answeredCount = Object.keys(answers).length;
  const current = questions[currentIndex] ?? questions[0];
  const visibleStage = stage === "exam" && remaining === 0 ? "complete" : stage;
  const completion = Math.round((answeredCount / questions.length) * 100);
  const domainCounts = useMemo(
    () =>
      (Object.keys(domainMeta) as Domain[]).map((domain) => ({
        domain,
        count: questions.filter((question) => question.domain === domain).length,
      })),
    [],
  );

  useEffect(() => {
    if (stage !== "exam" || remaining <= 0) return;
    const timer = window.setInterval(
      () => setRemaining((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [remaining, stage]);

  function startExam() {
    setCurrentIndex(0);
    setRemaining(45 * 60);
    setAnswers({});
    setFlagged(new Set());
    setStage("exam");
  }

  function toggleFlag() {
    setFlagged((previous) => {
      const next = new Set(previous);
      if (next.has(current.id)) next.delete(current.id);
      else next.add(current.id);
      return next;
    });
  }

  function chooseAnswer(answer: string) {
    setAnswers((previous) => ({ ...previous, [current.id]: answer }));
  }

  if (visibleStage === "intro") {
    return (
      <div className="cert-experience cert-intro">
        <section className="cert-intro__hero">
          <span className="cert-kicker">RIGOR TECHNICAL CERTIFICATION</span>
          <h1>
            Mock <em>Exam</em>
          </h1>
          <p>
            A focused rehearsal for senior and staff-level interviews. Work through
            realistic scenarios, commit to a decision, and keep moving under time.
          </p>
          <div className="cert-metrics" aria-label="Exam format">
            <div><strong>4</strong><span>domains</span></div>
            <div><strong>12</strong><span>questions</span></div>
            <div><strong>45</strong><span>minutes</span></div>
            <div><strong>70%</strong><span>target</span></div>
          </div>
        </section>

        <section className="cert-intro__panel">
          <div className="cert-section-heading">
            <span>CHOOSE YOUR SETTING</span>
            <h2>One deliberate sitting. No noisy dashboard.</h2>
          </div>
          <div className="cert-mode-grid">
            <article className="cert-mode cert-mode--selected">
              <span>RECOMMENDED</span>
              <Sparkles size={20} />
              <h3>Full-length assessment</h3>
              <p>Balanced coverage with enough time pressure to expose decision habits.</p>
              <strong>45 minutes · 12 questions</strong>
            </article>
            <article className="cert-mode">
              <ShieldCheck size={20} />
              <h3>Evidence-first scoring</h3>
              <p>Your selections remain local in this build; no recording or model transfer.</p>
              <strong>Deterministic session</strong>
            </article>
          </div>

          <div className="cert-domain-summary">
            <span>DOMAIN WEIGHTING</span>
            {domainCounts.map(({ domain, count }) => (
              <div key={domain}>
                <i className={`cert-dot cert-dot--${domainMeta[domain].accent}`} />
                <strong>{domainMeta[domain].label}</strong>
                <span>{count} questions</span>
                <em>{Math.round((count / questions.length) * 100)}%</em>
              </div>
            ))}
          </div>

          <div className="cert-rules">
            <strong>Before you begin</strong>
            <p>
              Choose the strongest answer, flag uncertain decisions, and complete the
              exam without external assistance. You can move freely between questions.
            </p>
          </div>
          <button className="cert-primary" onClick={startExam} type="button">
            Start mock exam <ArrowRight size={16} />
          </button>
        </section>
      </div>
    );
  }

  if (visibleStage === "complete") {
    return (
      <div className="cert-experience cert-complete">
        <div className="cert-complete__mark"><CheckCircle2 size={30} /></div>
        <span className="cert-kicker">SESSION COMPLETE</span>
        <h1>Decisions captured.</h1>
        <p>
          You answered {answeredCount} of {questions.length} questions and flagged {flagged.size}
          {flagged.size === 1 ? " item" : " items"} for review.
        </p>
        <div className="cert-complete__metrics">
          <div><strong>{completion}%</strong><span>completion</span></div>
          <div><strong>{formatTime(45 * 60 - remaining)}</strong><span>elapsed</span></div>
          <div><strong>{flagged.size}</strong><span>flagged</span></div>
        </div>
        <div className="cert-complete__actions">
          <button
            className="cert-secondary"
            onClick={() => {
              setRemaining((value) => Math.max(value, 1));
              setStage("exam");
            }}
            type="button"
          >
            <ArrowLeft size={15} /> Review responses
          </button>
          <button className="cert-primary" onClick={startExam} type="button">
            <RotateCcw size={15} /> Retake exam
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="cert-experience cert-exam">
      <aside className="cert-navigator">
        <div className="cert-navigator__heading">
          <span>TECHNICAL CERTIFICATION</span>
          <strong>Exam navigator</strong>
        </div>
        <div className="cert-legend">
          {(Object.keys(domainMeta) as Domain[]).map((domain) => (
            <div key={domain}>
              <i className={`cert-dot cert-dot--${domainMeta[domain].accent}`} />
              <span>{domainMeta[domain].label}</span>
            </div>
          ))}
        </div>
        <div className="cert-number-grid" aria-label="Question navigator">
          {questions.map((question, index) => {
            const isCurrent = index === currentIndex;
            const isAnswered = Boolean(answers[question.id]);
            const isFlagged = flagged.has(question.id);
            return (
              <button
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`Question ${index + 1}${isAnswered ? ", answered" : ""}${isFlagged ? ", flagged" : ""}`}
                className={[
                  "cert-number",
                  `cert-number--${domainMeta[question.domain].accent}`,
                  isCurrent ? "cert-number--current" : "",
                  isAnswered ? "cert-number--answered" : "",
                  isFlagged ? "cert-number--flagged" : "",
                ].filter(Boolean).join(" ")}
                key={question.id}
                onClick={() => setCurrentIndex(index)}
                type="button"
              >
                {isAnswered ? <Check size={12} /> : index + 1}
                {isFlagged && <Flag size={9} />}
              </button>
            );
          })}
        </div>
        <div className="cert-navigator__progress">
          <span><strong>{answeredCount}</strong> / {questions.length} answered</span>
          <div><i style={{ width: `${completion}%` }} /></div>
        </div>
        <button className="cert-submit" onClick={() => setStage("complete")} type="button">
          Submit exam
        </button>
      </aside>

      <main className="cert-question">
        <header className="cert-question__topbar">
          <div>
            <span>QUESTION {currentIndex + 1} OF {questions.length}</span>
            <strong>{domainMeta[current.domain].label}</strong>
          </div>
          <div className="cert-question__tools">
            <button
              aria-pressed={flagged.has(current.id)}
              className={flagged.has(current.id) ? "is-active" : ""}
              onClick={toggleFlag}
              type="button"
            >
              <Flag size={14} /> {flagged.has(current.id) ? "Flagged" : "Flag"}
            </button>
            <span className={remaining < 5 * 60 ? "is-urgent" : ""}>
              <Clock3 size={15} /> {formatTime(remaining)}
            </span>
          </div>
        </header>

        <article className="cert-question__body">
          <span className="cert-kicker">{current.eyebrow}</span>
          <h1>{current.title}</h1>
          <div className="cert-scenario">
            <span>SCENARIO</span>
            <p>{current.scenario}</p>
          </div>
          <fieldset className="cert-answers">
            <legend>Select the strongest answer.</legend>
            {current.answers.map((answer, index) => {
              const selected = answers[current.id] === answer;
              return (
                <label className={selected ? "cert-answer cert-answer--selected" : "cert-answer"} key={answer}>
                  <input
                    checked={selected}
                    name={current.id}
                    onChange={() => chooseAnswer(answer)}
                    type="radio"
                    value={answer}
                  />
                  <span>{String.fromCharCode(65 + index)}</span>
                  <p>{answer}</p>
                  <i>{selected && <Check size={14} />}</i>
                </label>
              );
            })}
          </fieldset>
        </article>

        <footer className="cert-question__footer">
          <button
            className="cert-secondary"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((index) => Math.max(0, index - 1))}
            type="button"
          >
            <ArrowLeft size={15} /> Previous
          </button>
          <div aria-label="Exam progress">
            {questions.map((question, index) => (
              <button
                aria-label={`Go to question ${index + 1}`}
                className={index === currentIndex ? "is-current" : answers[question.id] ? "is-answered" : ""}
                key={question.id}
                onClick={() => setCurrentIndex(index)}
                type="button"
              />
            ))}
          </div>
          {currentIndex < questions.length - 1 ? (
            <button
              className="cert-primary"
              onClick={() => setCurrentIndex((index) => Math.min(questions.length - 1, index + 1))}
              type="button"
            >
              Next <ArrowRight size={15} />
            </button>
          ) : (
            <button className="cert-primary" onClick={() => setStage("complete")} type="button">
              Finish <CheckCircle2 size={15} />
            </button>
          )}
        </footer>
      </main>
    </div>
  );
}
