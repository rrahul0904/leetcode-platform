"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Lightbulb,
  LoaderCircle,
  Play,
  Send,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-ui";
import {
  autosavePracticeSession,
  createPracticeSession,
  getPublishedQuestion,
  revealPracticeHint,
  runPracticeCode,
  submitPracticeCode,
  type CandidateSubmission,
  type ExecutionResult,
  type PracticeSession,
} from "@/lib/api";

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function ResultPanel({
  execution,
  submission,
}: {
  execution: ExecutionResult | null;
  submission: CandidateSubmission | null;
}) {
  if (!execution) {
    return (
      <div className="workspace-empty">
        <Play size={18} />
        <strong>Run your code to see public test results.</strong>
        <span>Hidden tests are evaluated only on submission.</span>
      </div>
    );
  }
  const passed = execution.state === "PASSED";
  return (
    <div className="execution-report">
      <div className={`execution-summary ${passed ? "is-passed" : "is-failed"}`}>
        {passed ? <CheckCircle2 size={19} /> : <CircleAlert size={19} />}
        <div>
          <strong>{passed ? "All evaluated tests passed" : "Review the failing cases"}</strong>
          <span>{execution.candidate_message ?? "Execution finished."}</span>
        </div>
        <small>{execution.runtime_ms ?? 0} ms</small>
      </div>
      <div className="test-results">
        {execution.public_results.map((test) => (
          <article key={test.test_id}>
            <span className={test.passed ? "test-pass" : "test-fail"}>
              {test.passed ? "PASS" : "FAIL"}
            </span>
            <strong>{test.name}</strong>
            {!test.passed && (
              <pre>
                {JSON.stringify(
                  { expected: test.expected, actual: test.actual },
                  null,
                  2,
                )}
              </pre>
            )}
          </article>
        ))}
      </div>
      {submission && (
        <div className="evaluation-score">
          <span>DETERMINISTIC EVALUATION</span>
          <strong>{Math.round(submission.evaluation.overall_score * 100)}%</strong>
          <p>
            Correctness {Math.round(submission.evaluation.correctness_score * 100)}%
            · Quality {Math.round(submission.evaluation.code_quality_score * 100)}%
            · Robustness {Math.round(submission.evaluation.robustness_score * 100)}%
          </p>
          <Link href="/progress">View updated readiness →</Link>
        </div>
      )}
    </div>
  );
}

export function PracticeWorkspace({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [source, setSource] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [execution, setExecution] = useState<ExecutionResult | null>(null);
  const [submission, setSubmission] = useState<CandidateSubmission | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [notice, setNotice] = useState("Starting practice session…");
  const initialized = useRef(false);

  const sessionMutation = useMutation({
    mutationFn: () => createPracticeSession(slug),
    onSuccess: (created) => {
      setSession(created);
      setSource(created.draft_code);
      setElapsed(created.elapsed_seconds);
      setNotice("Saved");
    },
    onError: () => setNotice("Could not start the session"),
  });
  const runMutation = useMutation({
    mutationFn: () => runPracticeCode(slug, session!.id, source),
    onSuccess: (result) => {
      setExecution(result);
      setSubmission(null);
      setNotice("Run completed");
    },
    onError: () => setNotice("Execution failed to start"),
  });
  const submitMutation = useMutation({
    mutationFn: () =>
      submitPracticeCode(
        slug,
        session!.id,
        source,
        `candidate-submit-${crypto.randomUUID()}`,
      ),
    onSuccess: (result) => {
      setExecution(result.execution);
      setSubmission(result);
      setNotice("Submission evaluated and saved");
      void queryClient.invalidateQueries({ queryKey: ["candidate-readiness"] });
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
    },
    onError: () => setNotice("Submission could not be evaluated"),
  });
  const hintMutation = useMutation({
    mutationFn: () => revealPracticeHint(session!.id),
    onSuccess: (result) => setHint(result.text),
    onError: () => setHint("No additional hint is available."),
  });

  useEffect(() => {
    if (!question.data || initialized.current) return;
    initialized.current = true;
    sessionMutation.mutate();
  }, [question.data, sessionMutation]);

  useEffect(() => {
    if (!session || submission) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [session, submission]);

  useEffect(() => {
    if (!session || !source || submission) return;
    const autosave = window.setTimeout(() => {
      void autosavePracticeSession(session.id, {
        draft_code: source,
        elapsed_seconds: elapsed,
      })
        .then(() => setNotice("Saved"))
        .catch(() => setNotice("Autosave unavailable"));
    }, 900);
    return () => window.clearTimeout(autosave);
  }, [elapsed, session, source, submission]);

  if (question.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Preparing practice workspace" />
      </div>
    );
  if (question.isError || !question.data)
    return (
      <div className="page-content">
        <ErrorState retry={() => void question.refetch()} />
      </div>
    );

  const item = question.data;
  const busy =
    !session || runMutation.isPending || submitMutation.isPending;
  return (
    <div className="practice-page">
      <header className="practice-header">
        <Link href={`/question-bank/${slug}`}>
          <ArrowLeft size={15} /> Leave workspace
        </Link>
        <div>
          <span>{item.external_id}</span>
          <strong>{item.title}</strong>
        </div>
        <div className="practice-timer">
          <Clock3 size={16} />
          <strong>{formatTime(elapsed)}</strong>
          <span>{notice}</span>
        </div>
      </header>
      <div className="practice-layout">
        <section className="prompt-pane">
          <div className="pane-heading">
            <span>PROBLEM</span>
            <small>{item.difficulty} · {item.estimated_duration_minutes} min</small>
          </div>
          <h1>{item.title}</h1>
          <p className="lead-copy">{item.problem_statement}</p>
          <h2>Instructions</h2>
          <ul>
            {item.candidate_instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ul>
          <h2>Constraints</h2>
          <ul>
            {item.public_constraints.map((constraint) => (
              <li key={constraint}>{constraint}</li>
            ))}
          </ul>
          {item.public_examples.map((example) => (
            <div className="practice-example" key={example.id}>
              <strong>{example.name}</strong>
              <pre>{JSON.stringify(example, null, 2)}</pre>
            </div>
          ))}
          <button
            className="hint-button"
            disabled={!session || hintMutation.isPending}
            onClick={() => hintMutation.mutate()}
          >
            <Lightbulb size={16} /> Reveal next hint
          </button>
          {hint && <div className="hint-copy">{hint}</div>}
        </section>
        <section className="editor-pane">
          <div className="pane-heading">
            <span>PYTHON 3.13</span>
            <small>Local functional runner</small>
          </div>
          <textarea
            aria-label="Python source code"
            className="code-editor"
            spellCheck={false}
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setNotice("Unsaved changes");
            }}
          />
          <div className="workspace-actions">
            <button
              className="button button--secondary"
              disabled={busy || !source}
              onClick={() => runMutation.mutate()}
            >
              {runMutation.isPending ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Play size={16} />
              )}
              Run public tests
            </button>
            <button
              className="button button--primary"
              disabled={busy || !source || Boolean(submission)}
              onClick={() => submitMutation.mutate()}
            >
              {submitMutation.isPending ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Send size={16} />
              )}
              Submit for evaluation
            </button>
          </div>
          <div className="result-pane">
            <div className="pane-heading">
              <span>RESULTS</span>
              <small>Hidden inputs never leave the server</small>
            </div>
            <ResultPanel execution={execution} submission={submission} />
          </div>
        </section>
      </div>
    </div>
  );
}
