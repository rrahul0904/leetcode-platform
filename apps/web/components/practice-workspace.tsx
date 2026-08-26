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
  Square,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  ControlledCodeEditor,
  type WorkspaceLanguage,
} from "@/components/controlled-code-editor";
import { ErrorState, LoadingState } from "@/components/page-ui";
import {
  cancelExecution,
  createRuntimePracticeSession,
  getCompletedSubmission,
  getExecution,
  isTerminalExecution,
  queueRunExecution,
  queueSubmitExecution,
  type AsyncExecutionView,
  type ExecutionAccepted,
  type SubmissionRuntime,
} from "@/lib/async-execution";
import {
  autosavePracticeSession,
  getPublishedQuestion,
  revealPracticeHint,
  type CandidateSubmission,
  type PracticeSession,
} from "@/lib/api";

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function runtimeForTrack(track: string): SubmissionRuntime {
  const normalized = track.trim().toLowerCase();
  return normalized.includes("sql") || normalized.includes("database")
    ? "postgresql18"
    : "python3.13";
}

function languageForRuntime(runtime: SubmissionRuntime): WorkspaceLanguage {
  return runtime === "postgresql18" ? "sql" : "python";
}

function ResultPanel({
  execution,
  submission,
}: {
  execution: AsyncExecutionView | null;
  submission: CandidateSubmission | null;
}) {
  if (!execution) {
    return (
      <div className="workspace-empty">
        <Play size={18} />
        <strong>Run your code to see public test results.</strong>
        <span>Hidden answers never enter the candidate sandbox.</span>
      </div>
    );
  }

  if (!isTerminalExecution(execution.status)) {
    return (
      <div className="workspace-empty">
        <LoaderCircle className="spin" size={18} />
        <strong>
          {execution.status === "QUEUED" ? "Execution queued" : "Running securely"}
        </strong>
        <span>
          Your editor stays responsive while the isolated worker handles this request.
        </span>
      </div>
    );
  }

  const result = execution.result;
  const publicPassed = result?.public_results.every((test) => test.passed) ?? false;
  const hiddenPassed = result != null && result.hidden_total === result.hidden_passed;
  const passed =
    execution.status === "COMPLETED" && result != null && publicPassed && hiddenPassed;

  return (
    <div className="execution-report">
      <div className={`execution-summary ${passed ? "is-passed" : "is-failed"}`}>
        {passed ? <CheckCircle2 size={19} /> : <CircleAlert size={19} />}
        <div>
          <strong>
            {passed
              ? "All evaluated tests passed"
              : execution.status === "COMPLETED"
                ? "Review the failing cases"
                : `Execution ${execution.status.toLowerCase()}`}
          </strong>
          <span>
            {result?.candidate_message ??
              (execution.error
                ? `Execution could not complete (${execution.error}).`
                : "Execution finished.")}
          </span>
        </div>
        <small>{execution.runtime_ms ?? 0} ms</small>
      </div>
      <div className="test-results">
        {result?.public_results.map((test) => (
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
      {(result?.stdout || result?.stderr) && (
        <div className="execution-console">
          <span>CONSOLE</span>
          {result.stdout && <pre>{result.stdout}</pre>}
          {result.stderr && <pre className="is-error">{result.stderr}</pre>}
        </div>
      )}
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

type ActiveExecutionKind = "run" | "submit";

type StoredExecution = {
  executionId: string;
  kind: ActiveExecutionKind;
};

export function PracticeWorkspace({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });
  const runtime = runtimeForTrack(question.data?.track ?? "");
  const language = languageForRuntime(runtime);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [source, setSource] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [lastExecution, setLastExecution] = useState<AsyncExecutionView | null>(null);
  const [submission, setSubmission] = useState<CandidateSubmission | null>(null);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [activeKind, setActiveKind] = useState<ActiveExecutionKind | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [notice, setNotice] = useState("Starting practice session…");
  const initialized = useRef(false);
  const pollStartedAt = useRef<number | null>(null);
  const runIdempotencyKey = useRef<string | null>(null);
  const submitIdempotencyKey = useRef<string | null>(null);
  const storageKey = `rigor.active-execution:${slug}`;

  function rememberExecution(accepted: ExecutionAccepted, kind: ActiveExecutionKind) {
    const stored: StoredExecution = {
      executionId: accepted.execution_id,
      kind,
    };
    window.localStorage.setItem(storageKey, JSON.stringify(stored));
    pollStartedAt.current = Date.now();
    setActiveExecutionId(accepted.execution_id);
    setActiveKind(kind);
    setLastExecution(null);
    setSubmission(null);
  }

  function restoreExecution() {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return;
    try {
      const stored = JSON.parse(raw) as Partial<StoredExecution>;
      if (
        typeof stored.executionId === "string" &&
        (stored.kind === "run" || stored.kind === "submit")
      ) {
        pollStartedAt.current = Date.now();
        setActiveExecutionId(stored.executionId);
        setActiveKind(stored.kind);
        setNotice("Recovering active execution…");
      }
    } catch {
      window.localStorage.removeItem(storageKey);
    }
  }

  const sessionMutation = useMutation({
    mutationFn: () => createRuntimePracticeSession(slug, runtime),
    onSuccess: (created) => {
      setSession(created);
      setSource(created.draft_code);
      setElapsed(created.elapsed_seconds);
      setNotice("Saved");
      restoreExecution();
    },
    onError: () => setNotice("Could not start the session"),
  });

  const executionQuery = useQuery({
    queryKey: ["candidate-execution", activeExecutionId],
    queryFn: ({ signal }) => getExecution(activeExecutionId!, signal),
    enabled: Boolean(activeExecutionId),
    refetchInterval: (query) => {
      const current = query.state.data;
      if (!activeExecutionId || (current && isTerminalExecution(current.status))) {
        return false;
      }
      const started = pollStartedAt.current ?? Date.now();
      const pollingFor = Date.now() - started;
      if (pollingFor < 3_000) return 500;
      if (pollingFor < 10_000) return 1_000;
      return 2_000;
    },
    refetchIntervalInBackground: false,
    retry: 3,
  });

  const runMutation = useMutation({
    mutationFn: () => {
      const key = runIdempotencyKey.current ?? `candidate-run-${crypto.randomUUID()}`;
      runIdempotencyKey.current = key;
      return queueRunExecution(slug, session!.id, source, key);
    },
    onSuccess: (accepted) => {
      runIdempotencyKey.current = null;
      rememberExecution(accepted, "run");
      setNotice(accepted.duplicate ? "Run already queued" : "Run queued");
    },
    onError: () => setNotice("Execution could not be queued; retry is safe"),
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      const key =
        submitIdempotencyKey.current ?? `candidate-submit-${crypto.randomUUID()}`;
      submitIdempotencyKey.current = key;
      return queueSubmitExecution(slug, session!.id, source, runtime, key);
    },
    onSuccess: (accepted) => {
      submitIdempotencyKey.current = null;
      rememberExecution(accepted, "submit");
      setNotice(
        accepted.duplicate ? "Submission already queued" : "Submission queued",
      );
    },
    onError: () => setNotice("Submission could not be queued; retry is safe"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelExecution(activeExecutionId!),
    onMutate: () => setNotice("Cancelling execution…"),
    onSuccess: (cancelled) => {
      setLastExecution(cancelled);
      setNotice(
        cancelled.status === "CANCELLED"
          ? "Execution cancelled"
          : "Execution already finished",
      );
      window.localStorage.removeItem(storageKey);
      setActiveExecutionId(null);
      setActiveKind(null);
    },
    onError: () => setNotice("Cancellation could not be confirmed"),
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
    const current = executionQuery.data;
    if (!current) return;

    queueMicrotask(() => {
      setLastExecution(current);
      if (!isTerminalExecution(current.status)) {
        setNotice(
          current.status === "QUEUED"
            ? "Waiting for isolated runner…"
            : "Running in isolated sandbox…",
        );
        return;
      }

      window.localStorage.removeItem(storageKey);
      setActiveExecutionId(null);
      const completedKind = activeKind;
      setActiveKind(null);
      if (current.status === "COMPLETED") {
        setNotice(completedKind === "submit" ? "Submission evaluated" : "Run completed");
      } else {
        setNotice(`Execution ${current.status.toLowerCase()}`);
      }

      if (completedKind === "submit" && current.submission_id) {
        void getCompletedSubmission(current.submission_id)
          .then((saved) => {
            setSubmission(saved);
            void queryClient.invalidateQueries({ queryKey: ["candidate-readiness"] });
            void queryClient.invalidateQueries({ queryKey: ["submissions"] });
          })
          .catch(() =>
            setNotice("Execution finished; submission summary is still syncing"),
          );
      }
    });
  }, [activeKind, executionQuery.data, queryClient, storageKey]);

  useEffect(() => {
    const submitInFlight = activeKind === "submit";
    if (!session || submission || submitInFlight) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [activeKind, session, submission]);

  useEffect(() => {
    if (!session || !source || submission || activeKind === "submit") return;
    const autosave = window.setTimeout(() => {
      void autosavePracticeSession(session.id, {
        draft_code: source,
        elapsed_seconds: elapsed,
      })
        .then(() => setNotice("Saved"))
        .catch(() => setNotice("Autosave unavailable"));
    }, 900);
    return () => window.clearTimeout(autosave);
  }, [activeKind, elapsed, session, source, submission]);

  if (question.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Preparing practice workspace" />
      </div>
    );
  }
  if (question.isError || !question.data) {
    return (
      <div className="page-content">
        <ErrorState retry={() => void question.refetch()} />
      </div>
    );
  }

  const item = question.data;
  const execution = executionQuery.data ?? lastExecution;
  const busy =
    !session || runMutation.isPending || submitMutation.isPending || Boolean(activeExecutionId);
  const starterSource = item.starter_code ?? "";

  function updateSource(nextSource: string) {
    setSource(nextSource);
    runIdempotencyKey.current = null;
    submitIdempotencyKey.current = null;
    setNotice("Unsaved changes");
  }

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
            <small>
              {item.difficulty} · {item.estimated_duration_minutes} min
            </small>
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
          <ControlledCodeEditor
            language={language}
            source={source}
            starterSource={starterSource}
            disabled={Boolean(submission)}
            saveState={notice}
            onChange={updateSource}
            onRun={() => runMutation.mutate()}
            onSubmit={() => submitMutation.mutate()}
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
            {activeExecutionId && (
              <button
                className="button button--secondary"
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate()}
              >
                {cancelMutation.isPending ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Square size={14} />
                )}
                Cancel execution
              </button>
            )}
          </div>
          <ResultPanel execution={execution} submission={submission} />
        </section>
      </div>
    </div>
  );
}
