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
  ShieldAlert,
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
import {
  getExecutionCapability,
  type ExecutionCapability,
} from "@/lib/execution-capability";

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function languageForRuntime(runtime: SubmissionRuntime): WorkspaceLanguage {
  return runtime === "postgresql18" ? "sql" : "python";
}

function runtimeLabel(runtime: SubmissionRuntime) {
  return runtime === "postgresql18" ? "PostgreSQL 18" : "Python 3.13";
}

type ActiveExecutionKind = "run" | "submit";
type DraftSaveState =
  | "Starting practice session…"
  | "Saved"
  | "Unsaved changes"
  | "Saving…"
  | "Save unavailable";

type StoredExecution = {
  executionId: string;
  kind: ActiveExecutionKind;
};

function HostedOnlyBoundary({
  slug,
  capability,
}: {
  slug: string;
  capability: ExecutionCapability;
}) {
  return (
    <div className="page-content">
      <Link className="back-link" href={`/question-bank/${slug}`}>
        <ArrowLeft size={15} /> Back to question
      </Link>
      <section className="panel section-block">
        <span className="eyebrow">HOSTED PRACTICE</span>
        <h1>This question is not runnable yet.</h1>
        <p className="lead-copy">
          SkillsForge AI only enables Run and Submit when the published question version
          has a supported isolated runtime and deterministic test evidence.
        </p>
        <div className="boundary-note">
          <ShieldAlert size={18} />
          <div>
            <strong>{capability.reason ?? "Execution is unavailable for this version."}</strong>
            <p>
              No simulated PASS result will be shown. You can still review the prompt and
              solution from the Question Bank.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
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
        <strong>Run your solution to see deterministic results.</strong>
        <span>Hidden expected answers never enter the candidate sandbox.</span>
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
        <span>The isolated runner is processing this execution.</span>
      </div>
    );
  }

  const result = execution.result;
  const evaluatedTestCount =
    (result?.public_results.length ?? 0) + (result?.hidden_total ?? 0);
  const publicPassed = result?.public_results.every((test) => test.passed) ?? false;
  const hiddenPassed = result != null && result.hidden_total === result.hidden_passed;
  const passed =
    execution.status === "COMPLETED" &&
    result != null &&
    evaluatedTestCount > 0 &&
    publicPassed &&
    hiddenPassed;
  const completedWithoutEvidence =
    execution.status === "COMPLETED" && result != null && evaluatedTestCount === 0;

  return (
    <div className="execution-report">
      <div className={`execution-summary ${passed ? "is-passed" : "is-failed"}`}>
        {passed ? <CheckCircle2 size={19} /> : <CircleAlert size={19} />}
        <div>
          <strong>
            {passed
              ? "All evaluated tests passed"
              : completedWithoutEvidence
                ? "No deterministic test evidence returned"
                : execution.status === "COMPLETED"
                  ? "Review the failing cases"
                  : `Execution ${execution.status.toLowerCase()}`}
          </strong>
          <span>
            {completedWithoutEvidence
              ? "SkillsForge AI will not mark this run as passed without evaluated tests."
              : result?.candidate_message ??
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
          <Link href="/progress">View updated progress →</Link>
        </div>
      )}
    </div>
  );
}

export function SkillsForgePracticeWorkspace({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });
  const capability = useQuery({
    queryKey: ["execution-capability", slug],
    queryFn: ({ signal }) => getExecutionCapability(slug, signal),
  });

  const runnableCapability =
    capability.data?.availability === "runnable" && capability.data.runtime
      ? capability.data
      : null;
  const runtime = runnableCapability?.runtime ?? null;
  const language = runtime ? languageForRuntime(runtime) : "python";

  const [session, setSession] = useState<PracticeSession | null>(null);
  const [source, setSource] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [lastExecution, setLastExecution] = useState<AsyncExecutionView | null>(null);
  const [submission, setSubmission] = useState<CandidateSubmission | null>(null);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [activeKind, setActiveKind] = useState<ActiveExecutionKind | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<DraftSaveState>(
    "Starting practice session…",
  );
  const [executionNotice, setExecutionNotice] = useState("Preparing workspace…");

  const initialized = useRef(false);
  const pollStartedAt = useRef<number | null>(null);
  const runIdempotencyKey = useRef<string | null>(null);
  const submitIdempotencyKey = useRef<string | null>(null);
  const lastSavedSource = useRef("");
  const lastSavedElapsed = useRef(0);
  const elapsedRef = useRef(0);

  function executionStorageKey(sessionId: string) {
    return `skillsforge.active-execution:${sessionId}`;
  }

  function clearStoredExecution(sessionId?: string) {
    const id = sessionId ?? session?.id;
    if (id) window.localStorage.removeItem(executionStorageKey(id));
  }

  function restoreExecution(sessionId: string) {
    const storageKey = executionStorageKey(sessionId);
    const raw = window.localStorage.getItem(storageKey);
    window.localStorage.removeItem(`rigor.active-execution:${slug}`);
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
        setExecutionNotice("Recovering active execution…");
      }
    } catch {
      window.localStorage.removeItem(storageKey);
    }
  }

  function rememberExecution(accepted: ExecutionAccepted, kind: ActiveExecutionKind) {
    if (!session) return;
    const stored: StoredExecution = {
      executionId: accepted.execution_id,
      kind,
    };
    window.localStorage.setItem(
      executionStorageKey(session.id),
      JSON.stringify(stored),
    );
    pollStartedAt.current = Date.now();
    setActiveExecutionId(accepted.execution_id);
    setActiveKind(kind);
    setLastExecution(null);
    setSubmission(null);
  }

  const sessionMutation = useMutation({
    mutationFn: () => createRuntimePracticeSession(slug, runtime!),
    onSuccess: (created) => {
      setSession(created);
      setSource(created.draft_code);
      setElapsed(created.elapsed_seconds);
      elapsedRef.current = created.elapsed_seconds;
      lastSavedSource.current = created.draft_code;
      lastSavedElapsed.current = created.elapsed_seconds;
      setSaveState("Saved");
      setExecutionNotice("Ready");
      restoreExecution(created.id);
    },
    onError: () => {
      setSaveState("Save unavailable");
      setExecutionNotice("Could not start the practice session");
    },
  });

  useEffect(() => {
    if (!question.data || !runnableCapability || !runtime || initialized.current) return;
    initialized.current = true;
    sessionMutation.mutate();
  }, [question.data, runnableCapability, runtime, sessionMutation]);

  useEffect(() => {
    elapsedRef.current = elapsed;
  }, [elapsed]);

  const executionQuery = useQuery({
    queryKey: ["candidate-execution", activeExecutionId],
    queryFn: ({ signal }) => getExecution(activeExecutionId!, signal),
    enabled: Boolean(activeExecutionId),
    refetchInterval: (query) => {
      const current = query.state.data;
      if (!activeExecutionId || (current && isTerminalExecution(current.status))) {
        return false;
      }
      const pollingFor = Date.now() - (pollStartedAt.current ?? Date.now());
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
      setExecutionNotice(accepted.duplicate ? "Run already queued" : "Run queued");
    },
    onError: () =>
      setExecutionNotice("Execution could not be queued; retry is safe"),
  });

  const submitMutation = useMutation({
    mutationFn: async () => {
      setSaveState("Saving…");
      try {
        const saved = await autosavePracticeSession(session!.id, {
          draft_code: source,
          elapsed_seconds: elapsedRef.current,
        });
        lastSavedSource.current = saved.draft_code;
        lastSavedElapsed.current = saved.elapsed_seconds;
        setSaveState("Saved");
      } catch {
        setSaveState("Save unavailable");
      }

      const key =
        submitIdempotencyKey.current ?? `candidate-submit-${crypto.randomUUID()}`;
      submitIdempotencyKey.current = key;
      return queueSubmitExecution(slug, session!.id, source, runtime!, key);
    },
    onSuccess: (accepted) => {
      submitIdempotencyKey.current = null;
      rememberExecution(accepted, "submit");
      setExecutionNotice(
        accepted.duplicate ? "Submission already queued" : "Submission queued",
      );
    },
    onError: () =>
      setExecutionNotice("Submission could not be queued; retry is safe"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelExecution(activeExecutionId!),
    onMutate: () => setExecutionNotice("Cancelling execution…"),
    onSuccess: (cancelled) => {
      setLastExecution(cancelled);
      setExecutionNotice(
        cancelled.status === "CANCELLED"
          ? "Execution cancelled"
          : "Execution already finished",
      );
      clearStoredExecution();
      setActiveExecutionId(null);
      setActiveKind(null);
    },
    onError: () => setExecutionNotice("Cancellation could not be confirmed"),
  });

  const hintMutation = useMutation({
    mutationFn: () => revealPracticeHint(session!.id),
    onSuccess: (result) => setHint(result.text),
    onError: () => setHint("No additional hint is available."),
  });

  useEffect(() => {
    const current = executionQuery.data;
    if (!current) return;

    queueMicrotask(() => {
      setLastExecution(current);
      if (!isTerminalExecution(current.status)) {
        setExecutionNotice(
          current.status === "QUEUED"
            ? "Waiting for isolated runner…"
            : "Running in isolated sandbox…",
        );
        return;
      }

      clearStoredExecution();
      setActiveExecutionId(null);
      const completedKind = activeKind;
      setActiveKind(null);
      setExecutionNotice(
        current.status === "COMPLETED"
          ? completedKind === "submit"
            ? "Submission evaluated"
            : "Run completed"
          : `Execution ${current.status.toLowerCase()}`,
      );

      if (completedKind === "submit" && current.submission_id) {
        void getCompletedSubmission(current.submission_id)
          .then((saved) => {
            setSubmission(saved);
            void queryClient.invalidateQueries({ queryKey: ["candidate-readiness"] });
            void queryClient.invalidateQueries({ queryKey: ["submissions"] });
            void queryClient.invalidateQueries({ queryKey: ["candidate-competencies"] });
            void queryClient.invalidateQueries({ queryKey: ["next-action"] });
          })
          .catch(() =>
            setExecutionNotice(
              "Execution finished; submission summary is still syncing",
            ),
          );
      }
    });
  }, [activeKind, executionQuery.data, queryClient, session]);

  useEffect(() => {
    if (!session || submission || activeKind === "submit") return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1_000);
    return () => window.clearInterval(timer);
  }, [activeKind, session, submission]);

  useEffect(() => {
    if (!session || submission || activeKind === "submit") return;
    if (source === lastSavedSource.current) return;

    const autosave = window.setTimeout(() => {
      setSaveState("Saving…");
      void autosavePracticeSession(session.id, {
        draft_code: source,
        elapsed_seconds: elapsedRef.current,
      })
        .then((saved) => {
          lastSavedSource.current = saved.draft_code;
          lastSavedElapsed.current = saved.elapsed_seconds;
          if (saved.draft_code === source) setSaveState("Saved");
        })
        .catch(() => setSaveState("Save unavailable"));
    }, 700);

    return () => window.clearTimeout(autosave);
  }, [activeKind, session, source, submission]);

  useEffect(() => {
    if (!session || submission || activeKind === "submit") return;
    const persistenceTimer = window.setInterval(() => {
      const currentElapsed = elapsedRef.current;
      if (
        currentElapsed === lastSavedElapsed.current &&
        source === lastSavedSource.current
      ) {
        return;
      }
      void autosavePracticeSession(session.id, {
        draft_code: source,
        elapsed_seconds: currentElapsed,
      })
        .then((saved) => {
          lastSavedSource.current = saved.draft_code;
          lastSavedElapsed.current = saved.elapsed_seconds;
          if (saved.draft_code === source) setSaveState("Saved");
        })
        .catch(() => setSaveState("Save unavailable"));
    }, 15_000);
    return () => window.clearInterval(persistenceTimer);
  }, [activeKind, session, source, submission]);

  if (question.isLoading || capability.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Preparing secure practice workspace" />
      </div>
    );
  }

  if (question.isError || !question.data || capability.isError || !capability.data) {
    return (
      <div className="page-content">
        <ErrorState
          retry={() => {
            void question.refetch();
            void capability.refetch();
          }}
        />
      </div>
    );
  }

  if (!runnableCapability || !runtime) {
    return <HostedOnlyBoundary slug={slug} capability={capability.data} />;
  }

  const item = question.data;
  const execution = executionQuery.data ?? lastExecution;
  const busy =
    !session || runMutation.isPending || submitMutation.isPending || Boolean(activeExecutionId);
  const starterSource = runnableCapability.starter_source;
  const hasSource = source.trim().length > 0;

  function updateSource(nextSource: string) {
    setSource(nextSource);
    runIdempotencyKey.current = null;
    submitIdempotencyKey.current = null;
    setSaveState("Unsaved changes");
  }

  return (
    <div className="practice-page">
      <header className="practice-header">
        <Link href={`/question-bank/${slug}`}>
          <ArrowLeft size={15} /> Leave workspace
        </Link>
        <div>
          <span>
            {item.external_id} · {runtimeLabel(runtime)}
          </span>
          <strong>{item.title}</strong>
        </div>
        <div className="practice-timer">
          <Clock3 size={16} />
          <strong>{formatTime(elapsed)}</strong>
          <span>
            {saveState} · {executionNotice}
          </span>
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
            type="button"
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
            saveState={saveState}
            onChange={updateSource}
            onRun={() => runMutation.mutate()}
            onSubmit={() => submitMutation.mutate()}
          />
          <div className="workspace-actions">
            <button
              className="button button--secondary"
              disabled={busy || !hasSource}
              onClick={() => runMutation.mutate()}
              type="button"
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
              disabled={busy || !hasSource || Boolean(submission)}
              onClick={() => submitMutation.mutate()}
              type="button"
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
                type="button"
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
