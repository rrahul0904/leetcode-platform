"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Code2,
  Flag,
  Lightbulb,
  ListChecks,
  LoaderCircle,
  Play,
  RotateCcw,
  Send,
  StickyNote,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  getKnowledgeProblem,
  getKnowledgeProblems,
  getKnowledgeSolutions,
} from "@/lib/knowledge-api";
import {
  getCandidateProblemState,
  patchCandidateProblemState,
  recordCandidateProblemActivity,
} from "@/lib/knowledge-progress-api";

function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function prose(value: string | null) {
  if (!value) {
    return ["The imported source did not contain a complete reviewed statement."];
  }
  return value
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PersistentKnowledgeProblemWorkspace({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const [elapsed, setElapsed] = useState(0);
  const [bookmarkOverride, setBookmarkOverride] = useState<boolean | null>(null);
  const [revisionOverride, setRevisionOverride] = useState<
    "none" | "marked" | "due" | "completed" | null
  >(null);
  const [activeTab, setActiveTab] = useState<
    "description" | "editorial" | "solutions" | "notes"
  >("description");
  const [selectedLanguage, setSelectedLanguage] = useState("");
  const [draft, setDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState<string | null>(null);
  const activityStarted = useRef(false);
  const lastRecordedSeconds = useRef(0);

  const problem = useQuery({
    queryKey: ["knowledge-problem", slug],
    queryFn: ({ signal }) => getKnowledgeProblem(slug, signal),
  });
  const candidateState = useQuery({
    queryKey: ["knowledge-candidate-state", slug],
    queryFn: ({ signal }) => getCandidateProblemState(slug, signal),
  });
  const navigator = useQuery({
    queryKey: ["knowledge-problem-navigator"],
    queryFn: ({ signal }) =>
      getKnowledgeProblems({ pageSize: 40, sort: "relevance" }, signal),
  });
  const availableLanguages = useMemo(
    () => problem.data?.languages ?? [],
    [problem.data?.languages],
  );
  const effectiveLanguage = selectedLanguage || availableLanguages[0] || "";
  const solutions = useQuery({
    queryKey: ["knowledge-solutions", slug, effectiveLanguage],
    queryFn: ({ signal }) =>
      getKnowledgeSolutions(slug, effectiveLanguage || undefined, signal),
    enabled: problem.data?.publication_status === "published",
  });

  const bookmarked = bookmarkOverride ?? candidateState.data?.bookmarked ?? false;
  const revisionStatus =
    revisionOverride ?? candidateState.data?.revision_status ?? "none";
  const flagged = revisionStatus === "marked" || revisionStatus === "due";
  const notes = noteDraft ?? candidateState.data?.private_notes ?? "";

  const bookmarkMutation = useMutation({
    mutationFn: (value: boolean) =>
      patchCandidateProblemState(slug, { bookmarked: value }),
    onSuccess: (state) => {
      setBookmarkOverride(null);
      queryClient.setQueryData(["knowledge-candidate-state", slug], state);
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-progress-summary"],
      });
    },
    onError: () => setBookmarkOverride(null),
  });
  const revisionMutation = useMutation({
    mutationFn: (value: "none" | "marked") =>
      patchCandidateProblemState(slug, { revision_status: value }),
    onSuccess: (state) => {
      setRevisionOverride(null);
      queryClient.setQueryData(["knowledge-candidate-state", slug], state);
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-progress-summary"],
      });
    },
    onError: () => setRevisionOverride(null),
  });
  const activityMutation = useMutation({
    mutationFn: (activity: Parameters<typeof recordCandidateProblemActivity>[1]) =>
      recordCandidateProblemActivity(slug, activity),
    onSuccess: (state) => {
      queryClient.setQueryData(["knowledge-candidate-state", slug], state);
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-progress-summary"],
      });
    },
  });

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activityStarted.current) return;
    activityStarted.current = true;
    const sessionId = crypto.randomUUID();
    void recordCandidateProblemActivity(slug, {
      event_type: "problem_viewed",
      idempotency_key: `view-${sessionId}`,
    });
    void recordCandidateProblemActivity(slug, {
      event_type: "session_started",
      language: effectiveLanguage || undefined,
      idempotency_key: `session-${sessionId}`,
    });
  }, [effectiveLanguage, slug]);

  useEffect(() => {
    const key = `rigor.knowledge-draft:${slug}:${effectiveLanguage || "general"}`;
    const restored = window.localStorage.getItem(key) ?? "";
    queueMicrotask(() => setDraft(restored));
  }, [effectiveLanguage, slug]);

  useEffect(() => {
    if (!draft) return;
    const key = `rigor.knowledge-draft:${slug}:${effectiveLanguage || "general"}`;
    const timeout = window.setTimeout(() => {
      window.localStorage.setItem(key, draft);
      void recordCandidateProblemActivity(slug, {
        event_type: "draft_saved",
        language: effectiveLanguage || undefined,
        idempotency_key: `draft-${crypto.randomUUID()}`,
        payload: { characters: draft.length },
      });
    }, 900);
    return () => window.clearTimeout(timeout);
  }, [draft, effectiveLanguage, slug]);

  useEffect(() => {
    if (noteDraft === null) return;
    const timeout = window.setTimeout(() => {
      void patchCandidateProblemState(slug, { private_notes: noteDraft }).then(
        (state) => {
          queryClient.setQueryData(["knowledge-candidate-state", slug], state);
          setNoteDraft(null);
        },
      );
    }, 900);
    return () => window.clearTimeout(timeout);
  }, [noteDraft, queryClient, slug]);

  useEffect(() => {
    if (elapsed - lastRecordedSeconds.current < 60) return;
    const seconds = elapsed - lastRecordedSeconds.current;
    lastRecordedSeconds.current = elapsed;
    void recordCandidateProblemActivity(slug, {
      event_type: "session_time_recorded",
      language: effectiveLanguage || undefined,
      duration_seconds: seconds,
      idempotency_key: `time-${crypto.randomUUID()}`,
    });
  }, [effectiveLanguage, elapsed, slug]);

  const index = navigator.data?.items.findIndex((item) => item.slug === slug) ?? -1;
  const previous = index > 0 ? navigator.data?.items[index - 1] : null;
  const next = index >= 0 ? navigator.data?.items[index + 1] : null;
  const selectedSolution = solutions.data?.[0];
  const executionReady = Boolean(selectedSolution?.is_executable);
  const questionNumbers = useMemo(
    () => navigator.data?.items.slice(0, 30) ?? [],
    [navigator.data?.items],
  );

  if (problem.isLoading) {
    return (
      <div className="kb-workspace-loading">
        <LoaderCircle className="spin" size={24} /> Preparing workspace
      </div>
    );
  }
  if (problem.isError || !problem.data) {
    return (
      <div className="kb-workspace-loading">
        <strong>This problem could not be opened.</strong>
        <Link href="/problems">Return to question bank</Link>
      </div>
    );
  }

  const item = problem.data;
  return (
    <div className="kb-workspace">
      <header className="kb-workspace-header">
        <Link href="/problems">
          <ChevronLeft size={15} /> Problems
        </Link>
        <div>
          <small>{item.external_id ?? item.canonical_key}</small>
          <strong>{item.title}</strong>
        </div>
        <span className={`kb-difficulty kb-difficulty--${item.difficulty ?? "unrated"}`}>
          {item.difficulty ?? "unrated"}
        </span>
        <div className="kb-workspace-clock">
          <Clock3 size={15} />
          <strong>{formatElapsed(elapsed)}</strong>
          <span>{activityMutation.isPending ? "Syncing evidence" : "Evidence saved"}</span>
        </div>
        <button
          className={flagged ? "is-active" : ""}
          disabled={revisionMutation.isPending}
          onClick={() => {
            const value = flagged ? "none" : "marked";
            setRevisionOverride(value);
            revisionMutation.mutate(value);
          }}
          type="button"
        >
          <Flag size={15} /> {flagged ? "Flagged" : "Flag"}
        </button>
      </header>

      <div className="kb-workspace-grid">
        <aside className="kb-question-navigator">
          <div>
            <span>QUESTION NAVIGATOR</span>
            <strong>{navigator.data?.total ?? 0} available</strong>
          </div>
          <section>
            <h2>Coding bank</h2>
            <div className="kb-number-grid">
              {questionNumbers.map((question, number) => (
                <Link
                  className={question.slug === slug ? "is-current" : ""}
                  href={`/problems/${question.slug}`}
                  key={question.id}
                  aria-label={`Open ${question.title}`}
                >
                  {number + 1}
                </Link>
              ))}
            </div>
          </section>
          <div className="kb-navigator-legend">
            <span><i className="current" /> Current</span>
            <span><i className="review" /> Review</span>
            <span><i /> Unanswered</span>
          </div>
          <Link className="kb-navigator-all" href="/problems">
            <ListChecks size={15} /> View all problems
          </Link>
        </aside>

        <main className="kb-question-pane">
          <nav className="kb-workspace-tabs" aria-label="Problem content">
            {(
              [
                ["description", "Description", ListChecks],
                ["editorial", "Editorial", Lightbulb],
                ["solutions", "Solutions", Code2],
                ["notes", "Notes", StickyNote],
              ] as const
            ).map(([value, label, Icon]) => (
              <button
                className={activeTab === value ? "is-active" : ""}
                key={value}
                onClick={() => setActiveTab(value)}
                type="button"
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </nav>

          {activeTab === "description" && (
            <article className="kb-problem-copy">
              <span className="kb-eyebrow">INTERVIEW QUESTION</span>
              <h1>{item.title}</h1>
              <div className="kb-tag-row">
                {item.topics.map((topic) => (
                  <em key={topic}>{topic.replaceAll("-", " ")}</em>
                ))}
                {item.companies.slice(0, 5).map((company) => (
                  <em key={company}>{company}</em>
                ))}
              </div>
              {prose(item.description).map((paragraph, paragraphIndex) => (
                <p key={paragraphIndex}>{paragraph}</p>
              ))}
              {item.examples.length > 0 && (
                <section>
                  <h2>Examples</h2>
                  {item.examples.map((example, exampleIndex) => (
                    <pre key={exampleIndex}>{JSON.stringify(example, null, 2)}</pre>
                  ))}
                </section>
              )}
              {item.constraints.length > 0 && (
                <section>
                  <h2>Constraints</h2>
                  <ul>
                    {item.constraints.map((constraint, constraintIndex) => (
                      <li key={constraintIndex}>{String(constraint)}</li>
                    ))}
                  </ul>
                </section>
              )}
              {item.publication_status === "metadata_only" && (
                <aside className="kb-source-notice">
                  This source-backed metadata record requires a reviewed hosted
                  statement, executable tests, and editorial before judge access.
                </aside>
              )}
            </article>
          )}

          {activeTab === "editorial" && (
            <div className="kb-tab-message">
              <Lightbulb size={20} />
              <strong>
                {item.editorial_available
                  ? "Editorial available after review"
                  : "Editorial in review"}
              </strong>
              <p>Approach explanations appear only after technical and rights review.</p>
            </div>
          )}

          {activeTab === "solutions" && (
            <div className="kb-solution-copy">
              {solutions.isLoading && <LoaderCircle className="spin" size={20} />}
              {selectedSolution ? (
                <>
                  <span>{selectedSolution.approach_name}</span>
                  <h2>{selectedSolution.language.toUpperCase()} solution</h2>
                  <p>
                    {selectedSolution.explanation ??
                      "Source-backed reviewed implementation."}
                  </p>
                  <div>
                    <strong>Time</strong>{" "}
                    {selectedSolution.time_complexity ?? "Not recorded"}
                    <strong>Space</strong>{" "}
                    {selectedSolution.space_complexity ?? "Not recorded"}
                  </div>
                  <pre>{selectedSolution.source_code}</pre>
                </>
              ) : (
                <div className="kb-tab-message">
                  <Code2 size={20} />
                  <strong>No reviewed solution is public yet.</strong>
                  <p>Imported code stays hidden until source and code review pass.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === "notes" && (
            <div className="kb-notes-panel">
              <label htmlFor="problem-notes">Private notes</label>
              <textarea
                id="problem-notes"
                placeholder="Capture assumptions, edge cases, mistakes, and revision cues."
                value={notes}
                onChange={(event) => setNoteDraft(event.target.value)}
              />
              <small>
                {noteDraft === null ? "Saved to your account" : "Saving notes…"}
              </small>
            </div>
          )}
        </main>

        <aside className="kb-editor-pane">
          <div className="kb-editor-toolbar">
            <label>
              <span>LANGUAGE</span>
              <select
                value={effectiveLanguage}
                onChange={(event) => setSelectedLanguage(event.target.value)}
              >
                {availableLanguages.length ? (
                  availableLanguages.map((value) => (
                    <option key={value} value={value}>
                      {value.toUpperCase()}
                    </option>
                  ))
                ) : (
                  <option value="">REFERENCE ONLY</option>
                )}
              </select>
            </label>
            <button
              aria-pressed={bookmarked}
              className={bookmarked ? "is-active" : ""}
              disabled={bookmarkMutation.isPending}
              onClick={() => {
                const value = !bookmarked;
                setBookmarkOverride(value);
                bookmarkMutation.mutate(value);
              }}
              type="button"
            >
              <Bookmark size={15} />
            </button>
            <button
              onClick={() => setDraft("")}
              type="button"
              aria-label="Reset draft"
            >
              <RotateCcw size={15} />
            </button>
          </div>
          <textarea
            aria-label="Solution draft"
            className="kb-code-editor"
            spellCheck={false}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              effectiveLanguage
                ? `Write your ${effectiveLanguage} solution here…`
                : "Choose a reviewed language solution to begin."
            }
          />
          <div className="kb-editor-actions">
            <button disabled={!executionReady || !draft} type="button">
              <Play size={15} /> Run tests
            </button>
            <button
              className="primary"
              disabled={!executionReady || !draft}
              type="button"
            >
              <Send size={15} /> Submit
            </button>
          </div>
          {!executionReady && (
            <p className="kb-execution-gate">
              Execution unlocks only after a reviewed runtime, starter contract,
              public tests, and hidden tests enter the isolated judge.
            </p>
          )}
        </aside>
      </div>

      <footer className="kb-workspace-footer">
        {previous ? (
          <Link href={`/problems/${previous.slug}`}>
            <ChevronLeft size={15} /> {previous.title}
          </Link>
        ) : (
          <span />
        )}
        <span>{flagged ? "Marked for review" : "Working session active"}</span>
        {next ? (
          <Link href={`/problems/${next.slug}`}>
            {next.title} <ChevronRight size={15} />
          </Link>
        ) : (
          <span />
        )}
      </footer>
    </div>
  );
}
