"use client";

import {
  AlertTriangle,
  CheckCircle2,
  FileCode2,
  GitPullRequest,
  MessageSquarePlus,
  ShieldAlert,
} from "lucide-react";
import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createReviewComment,
  createReviewSession,
  deleteReviewComment,
  getReviewChallenge,
  getReviewSession,
  listReviewSessions,
  submitReviewSession,
} from "@/lib/pr-review-api";
import type {
  PublicReviewChallenge,
  ReviewComment,
  ReviewGrade,
  ReviewSeverity,
  ReviewVerdict,
} from "@/lib/pr-review-lab";

import styles from "./pr-review-lab.module.css";

type SelectedLine = { file: string; line: number } | null;

const CHALLENGE_ID = "payments-retry-001";
const severityOptions: ReviewSeverity[] = ["info", "minor", "major", "blocker"];

function lineNumber(oldLine: number | null, newLine: number | null) {
  return newLine ?? oldLine ?? 0;
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function PrReviewLab() {
  const [challenge, setChallenge] = useState<PublicReviewChallenge | null>(null);
  const [activeFile, setActiveFile] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedLine, setSelectedLine] = useState<SelectedLine>(null);
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<ReviewSeverity>("major");
  const [verdict, setVerdict] = useState<ReviewVerdict>("request-changes");
  const [comments, setComments] = useState<ReviewComment[]>([]);
  const [grade, setGrade] = useState<ReviewGrade | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function restore() {
      try {
        const loadedChallenge = await getReviewChallenge(
          CHALLENGE_ID,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setChallenge(loadedChallenge);
        setActiveFile(loadedChallenge.files[0]?.path ?? "");

        const sessions = await listReviewSessions(controller.signal);
        const activeSession = sessions.find(
          (session) =>
            session.challengeId === CHALLENGE_ID
            && session.status === "active",
        );
        if (!activeSession || controller.signal.aborted) return;

        const detail = await getReviewSession(
          activeSession.id,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setSessionId(detail.session.id);
        setComments(detail.comments);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load PR Review Lab",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void restore();
    return () => controller.abort();
  }, []);

  const file = useMemo(
    () =>
      challenge?.files.find((item) => item.path === activeFile)
      ?? challenge?.files[0]
      ?? null,
    [activeFile, challenge],
  );

  function openComment(filePath: string, line: number) {
    if (grade) return;
    setSelectedLine({ file: filePath, line });
    setMessage("");
    setSeverity("major");
    setError(null);
  }

  async function addComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedMessage = message.trim();
    if (
      !selectedLine
      || !normalizedMessage
      || !challenge
      || saving
      || grade
    ) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const session = await createReviewSession(challenge.id);
        currentSessionId = session.id;
        setSessionId(session.id);
      }
      const persisted = await createReviewComment(currentSessionId, {
        file: selectedLine.file,
        line: selectedLine.line,
        severity,
        message: normalizedMessage,
      });
      setComments((current) => [...current, persisted]);
      setSelectedLine(null);
      setMessage("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to save review comment",
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeComment(comment: ReviewComment) {
    if (!sessionId || saving || grade) return;
    setSaving(true);
    setError(null);
    try {
      await deleteReviewComment(sessionId, comment.id);
      setComments((current) =>
        current.filter((candidate) => candidate.id !== comment.id),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to remove review comment",
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitReview() {
    if (!sessionId || comments.length === 0 || saving || grade) return;
    setSaving(true);
    setError(null);
    try {
      const submission = await submitReviewSession(sessionId, verdict);
      setGrade(submission.grade);
      setSelectedLine(null);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to submit review",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className={styles.shell}>
        <div className={styles.statusCard}>Loading PR Review Lab…</div>
      </section>
    );
  }

  if (!challenge || !file) {
    return (
      <section className={styles.shell}>
        <div className={styles.errorCard}>
          {error ?? "PR Review Lab challenge is unavailable."}
        </div>
      </section>
    );
  }

  return (
    <section className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <GitPullRequest size={14} /> ENGINEERING JUDGMENT
          </span>
          <h1>PR Review Lab</h1>
          <p>
            Review production-like changes, catch defects, calibrate severity, and make the
            merge call.
          </p>
        </div>
        <div className={styles.heroMeta}>
          <span>{challenge.difficulty}</span>
          <span>{challenge.estimatedMinutes} min</span>
          <span>{challenge.files.length} files changed</span>
        </div>
      </header>

      {error && <div className={styles.errorCard}>{error}</div>}

      <div className={styles.challengeBar}>
        <div>
          <span>
            {challenge.repository} · PR #{challenge.pullRequest}
          </span>
          <h2>{challenge.title}</h2>
          <p>{challenge.summary}</p>
        </div>
        <div className={styles.verdictControl}>
          <label htmlFor="review-verdict">Merge verdict</label>
          <select
            disabled={Boolean(grade)}
            id="review-verdict"
            value={verdict}
            onChange={(event) => setVerdict(event.target.value as ReviewVerdict)}
          >
            <option value="approve">Approve</option>
            <option value="comment">Comment</option>
            <option value="request-changes">Request changes</option>
          </select>
        </div>
      </div>

      <div className={styles.workspace}>
        <aside className={styles.fileRail} aria-label="Changed files">
          <div className={styles.railHeading}>Changed files</div>
          {challenge.files.map((candidate) => (
            <button
              className={candidate.path === file.path ? styles.activeFile : ""}
              key={candidate.path}
              onClick={() => {
                setActiveFile(candidate.path);
                setSelectedLine(null);
              }}
              type="button"
            >
              <FileCode2 size={15} />
              <span>{candidate.path.split("/").at(-1)}</span>
              <small>
                +{candidate.additions} −{candidate.deletions}
              </small>
            </button>
          ))}
          <div className={styles.reviewProgress}>
            <strong>{comments.length}</strong>
            <span>persisted review comments</span>
          </div>
        </aside>

        <main className={styles.diffPanel}>
          <div className={styles.fileHeader}>
            <span>{file.path}</span>
            <small>
              +{file.additions} −{file.deletions}
            </small>
          </div>
          <div className={styles.diff} role="table" aria-label={`Diff for ${file.path}`}>
            {file.lines.map((line, index) => {
              const targetLine = lineNumber(line.oldLine, line.newLine);
              const lineComments = comments.filter(
                (comment) => comment.file === file.path && comment.line === targetLine,
              );
              return (
                <div key={`${file.path}-${index}`}>
                  <div
                    className={`${styles.diffLine} ${styles[line.kind]}`}
                    role="row"
                  >
                    <span className={styles.lineNumber}>{line.oldLine ?? ""}</span>
                    <span className={styles.lineNumber}>{line.newLine ?? ""}</span>
                    <button
                      aria-label={`Review ${file.path} line ${targetLine}`}
                      className={styles.commentTrigger}
                      disabled={Boolean(grade)}
                      onClick={() => openComment(file.path, targetLine)}
                      type="button"
                    >
                      <MessageSquarePlus size={14} />
                    </button>
                    <code>
                      <span className={styles.marker}>
                        {line.kind === "addition"
                          ? "+"
                          : line.kind === "deletion"
                            ? "−"
                            : " "}
                      </span>
                      {line.content || " "}
                    </code>
                  </div>
                  {lineComments.map((comment) => (
                    <div className={styles.inlineComment} key={comment.id}>
                      <span className={`${styles.severity} ${styles[comment.severity]}`}>
                        {comment.severity}
                      </span>
                      <p>{comment.message}</p>
                      <button
                        disabled={saving || Boolean(grade)}
                        onClick={() => void removeComment(comment)}
                        type="button"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          {selectedLine?.file === file.path && !grade && (
            <form className={styles.composer} onSubmit={addComment}>
              <div>
                <strong>Comment on line {selectedLine.line}</strong>
                <button onClick={() => setSelectedLine(null)} type="button">
                  Cancel
                </button>
              </div>
              <textarea
                aria-label="Review comment"
                autoFocus
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Explain the failure mode, impact, and what should change…"
                rows={4}
                value={message}
              />
              <div>
                <label htmlFor="review-severity">Severity</label>
                <select
                  id="review-severity"
                  value={severity}
                  onChange={(event) => setSeverity(event.target.value as ReviewSeverity)}
                >
                  {severityOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <button
                  className={styles.primaryButton}
                  disabled={!message.trim() || saving}
                  type="submit"
                >
                  {saving ? "Saving…" : "Add comment"}
                </button>
              </div>
            </form>
          )}
        </main>

        <aside className={styles.summaryRail}>
          <div className={styles.summaryHeading}>
            <span>Review summary</span>
            <strong>{comments.length}</strong>
          </div>
          {comments.length === 0 ? (
            <div className={styles.emptyState}>
              <ShieldAlert size={24} />
              <p>
                Click a diff line to leave a finding. Strong reviews explain impact, not just
                style.
              </p>
            </div>
          ) : (
            <div className={styles.commentList}>
              {comments.map((comment) => (
                <article key={comment.id}>
                  <span className={`${styles.severity} ${styles[comment.severity]}`}>
                    {comment.severity}
                  </span>
                  <strong>
                    {comment.file.split("/").at(-1)}:{comment.line}
                  </strong>
                  <p>{comment.message}</p>
                </article>
              ))}
            </div>
          )}
          <button
            className={styles.submitButton}
            disabled={comments.length === 0 || saving || Boolean(grade)}
            onClick={() => void submitReview()}
            type="button"
          >
            {grade ? "Review submitted" : saving ? "Submitting…" : "Submit review"}
          </button>
        </aside>
      </div>

      {grade && (
        <section className={styles.gradePanel} aria-live="polite">
          <div className={styles.gradeHeadline}>
            <div>
              <span>Review scored server-side</span>
              <strong>
                {grade.score}
                <small>/100</small>
              </strong>
            </div>
            <p>
              {grade.caught.length} of {grade.caught.length + grade.missed.length} findings
              caught · {grade.missed.length} missed · {grade.falsePositiveCount} false positives
            </p>
          </div>
          <div className={styles.metrics}>
            <div>
              <span>Recall</span>
              <strong>{percent(grade.recall)}</strong>
            </div>
            <div>
              <span>Precision</span>
              <strong>{percent(grade.precision)}</strong>
            </div>
            <div>
              <span>Severity</span>
              <strong>{percent(grade.severityAccuracy)}</strong>
            </div>
            <div>
              <span>Merge call</span>
              <strong>{grade.verdictCorrect ? "Correct" : "Revisit"}</strong>
            </div>
          </div>
          <div className={styles.findingGrid}>
            <div>
              <h3>
                <CheckCircle2 size={17} /> Caught
              </h3>
              {grade.caught.length === 0 ? (
                <p>No hidden findings matched yet.</p>
              ) : (
                grade.caught.map((finding) => (
                  <article key={finding.id}>
                    <strong>{finding.title}</strong>
                    <span>
                      {finding.file.split("/").at(-1)}:{finding.line} · {finding.severity}
                    </span>
                    <p>{finding.explanation}</p>
                  </article>
                ))
              )}
            </div>
            <div>
              <h3>
                <AlertTriangle size={17} /> Missed
              </h3>
              {grade.missed.length === 0 ? (
                <p>Excellent: every hidden finding was caught.</p>
              ) : (
                grade.missed.map((finding) => (
                  <article key={finding.id}>
                    <strong>{finding.title}</strong>
                    <span>
                      {finding.file.split("/").at(-1)}:{finding.line} · {finding.severity}
                    </span>
                    <p>{finding.explanation}</p>
                  </article>
                ))
              )}
            </div>
          </div>
        </section>
      )}
    </section>
  );
}
