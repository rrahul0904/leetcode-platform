"use client";

import {
  CheckCircle2,
  CirclePause,
  CirclePlay,
  LoaderCircle,
  MessageSquareText,
  Send,
  ShieldCheck,
  Square,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  answerMockInterview,
  createMockInterview,
  getMockInterview,
  getMockInterviewTemplates,
  listMockInterviews,
  type MockInterviewSession,
  type MockInterviewSessionSummary,
  type MockInterviewTemplate,
  updateMockInterviewState,
} from "@/lib/mock-interview-api";

import styles from "./mock-interview-workspace.module.css";

export function MockInterviewWorkspace() {
  const [templates, setTemplates] = useState<MockInterviewTemplate[]>([]);
  const [selectedFocus, setSelectedFocus] = useState("");
  const [targetRole, setTargetRole] = useState("Senior Data Engineer");
  const [session, setSession] = useState<MockInterviewSession | null>(null);
  const [history, setHistory] = useState<MockInterviewSessionSummary[]>([]);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState<"load" | "create" | "answer" | "action" | null>(
    "load",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      getMockInterviewTemplates(controller.signal),
      listMockInterviews(controller.signal),
    ])
      .then(([items, sessions]) => {
        setTemplates(items);
        setHistory(sessions);
        const firstTemplate = items[0];
        if (firstTemplate) setSelectedFocus(firstTemplate.slug);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof Error ? caught.message : "Mock interviews failed to load.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(null);
      });
    return () => controller.abort();
  }, []);

  const template = useMemo(
    () => templates.find((item) => item.slug === selectedFocus) ?? null,
    [selectedFocus, templates],
  );
  const currentPrompt = useMemo(
    () =>
      [...(session?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "interviewer") ?? null,
    [session?.messages],
  );
  const answeredPhases = useMemo(
    () =>
      new Set(
        (session?.messages ?? [])
          .filter((message) => message.role === "candidate")
          .map((message) => message.phase),
      ),
    [session?.messages],
  );

  async function startInterview() {
    if (!template || !targetRole.trim() || busy) return;
    setBusy("create");
    setError(null);
    try {
      const created = await createMockInterview(
        template.slug,
        targetRole.trim(),
        crypto.randomUUID(),
      );
      setSession(created);
      setSelectedFocus(created.focus);
      setAnswer("");
      setHistory(await listMockInterviews());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Mock interview could not start.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function submitAnswer() {
    if (!session || !answer.trim() || busy || session.status !== "IN_PROGRESS") {
      return;
    }
    setBusy("answer");
    setError(null);
    try {
      const updated = await answerMockInterview(
        session.id,
        answer.trim(),
        crypto.randomUUID(),
      );
      setSession(updated);
      setAnswer("");
      setHistory(await listMockInterviews());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Response could not be submitted.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function act(action: "pause" | "resume" | "cancel") {
    if (!session || busy) return;
    setBusy("action");
    setError(null);
    try {
      setSession(await updateMockInterviewState(session.id, action));
      setHistory(await listMockInterviews());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Interview state could not be updated.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function openSession(sessionId: string) {
    if (busy) return;
    setBusy("load");
    setError(null);
    try {
      const opened = await getMockInterview(sessionId);
      setSession(opened);
      setSelectedFocus(opened.focus);
      setAnswer("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Interview could not be opened.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function refresh() {
    if (!session || busy) return;
    setBusy("load");
    setError(null);
    try {
      setSession(await getMockInterview(session.id));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Interview could not be refreshed.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (busy === "load" && templates.length === 0) {
    return (
      <section className={styles.shell}>
        <div className={styles.loading}>
          <LoaderCircle className={styles.spin} size={20} />
          Loading mock interview tracks…
        </div>
      </section>
    );
  }

  return (
    <section className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <MessageSquareText size={14} /> MOCK INTERVIEWS
          </span>
          <h1>Practice the conversation, not just the answer.</h1>
          <p>
            Choose a technical focus, work through structured interview phases, and
            turn scored evidence into SkillForge competency mastery and readiness.
          </p>
        </div>
        <div className={styles.trust}>
          <ShieldCheck size={18} />
          <div>
            <strong>Evidence-backed</strong>
            <span>Candidate-owned sessions · deterministic rubric · persisted report</span>
          </div>
        </div>
      </header>

      {!session ? (
        <div className={styles.setup}>
          <aside className={styles.templateRail}>
            <div className={styles.sectionTitle}>Interview focus</div>
            {templates.map((item) => (
              <button
                className={item.slug === selectedFocus ? styles.activeTemplate : ""}
                key={item.slug}
                onClick={() => setSelectedFocus(item.slug)}
                type="button"
              >
                <strong>{item.label}</strong>
                <span>{item.phases.length} phases</span>
              </button>
            ))}
            <div className={styles.sectionTitle}>Recent sessions</div>
            {history.length === 0 ? (
              <p className={styles.emptyHistory}>No interviews yet.</p>
            ) : (
              history.slice(0, 8).map((item) => (
                <button
                  className={styles.historyButton}
                  key={item.id}
                  onClick={() => void openSession(item.id)}
                  type="button"
                >
                  <strong>{item.focus_label}</strong>
                  <span>{item.status.replaceAll("_", " ")} · {item.target_role}</span>
                </button>
              ))
            )}
          </aside>

          <main className={styles.setupMain}>
            {template && (
              <>
                <span className={styles.eyebrow}>{template.label}</span>
                <h2>{template.description}</h2>
                <div className={styles.competencies}>
                  {template.competencies.map((competency) => (
                    <span key={competency}>{competency.replaceAll("-", " ")}</span>
                  ))}
                </div>

                <div className={styles.phaseList}>
                  {template.phases.map((phase, index) => (
                    <div key={phase.slug}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <strong>{phase.label}</strong>
                    </div>
                  ))}
                </div>

                <label className={styles.roleField}>
                  <span>Target role</span>
                  <input
                    maxLength={160}
                    onChange={(event) => setTargetRole(event.target.value)}
                    value={targetRole}
                  />
                </label>
                <button
                  className={styles.primary}
                  disabled={!targetRole.trim() || Boolean(busy)}
                  onClick={() => void startInterview()}
                  type="button"
                >
                  {busy === "create" ? (
                    <LoaderCircle className={styles.spin} size={16} />
                  ) : (
                    <CirclePlay size={16} />
                  )}
                  Start interview
                </button>
              </>
            )}
          </main>
        </div>
      ) : (
        <div className={styles.interviewLayout}>
          <aside className={styles.progressRail}>
            <div className={styles.sectionTitle}>Session</div>
            <div className={styles.sessionMeta}>
              <span>{session.focus_label}</span>
              <strong>{session.target_role}</strong>
              <small>{session.status.replaceAll("_", " ")}</small>
            </div>
            {(template?.phases ?? []).map((phase, index) => {
              const done = answeredPhases.has(phase.slug);
              const current = session.current_phase === phase.slug;
              return (
                <div
                  className={current ? styles.currentPhase : styles.phase}
                  key={phase.slug}
                >
                  <span>{done ? <CheckCircle2 size={15} /> : index + 1}</span>
                  <strong>{phase.label}</strong>
                </div>
              );
            })}

            <div className={styles.actions}>
              {session.status === "IN_PROGRESS" && (
                <button onClick={() => void act("pause")} type="button">
                  <CirclePause size={14} /> Pause
                </button>
              )}
              {session.status === "PAUSED" && (
                <button onClick={() => void act("resume")} type="button">
                  <CirclePlay size={14} /> Resume
                </button>
              )}
              {["IN_PROGRESS", "PAUSED"].includes(session.status) && (
                <button onClick={() => void act("cancel")} type="button">
                  <Square size={13} /> Cancel
                </button>
              )}
              <button onClick={() => void refresh()} type="button">
                Refresh
              </button>
            </div>
          </aside>

          <main className={styles.conversation}>
            {session.report ? (
              <section className={styles.report}>
                <span className={styles.eyebrow}>INTERVIEW COMPLETE</span>
                <div className={styles.score}>
                  <strong>{Math.round(session.report.overall_score * 100)}</strong>
                  <span>/100</span>
                </div>
                <h2>Your evidence report</h2>

                <div className={styles.reportGrid}>
                  <div>
                    <span>Strengths</span>
                    <ul>
                      {session.report.strengths.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <span>Growth areas</span>
                    <ul>
                      {session.report.growth_areas.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className={styles.nextSteps}>
                  <span>Next steps</span>
                  {session.report.next_steps.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
                <button
                  className={styles.primary}
                  onClick={() => {
                    setSession(null);
                    setAnswer("");
                    setError(null);
                  }}
                  type="button"
                >
                  Start another interview
                </button>
              </section>
            ) : (
              <>
                <div className={styles.promptCard}>
                  <span className={styles.eyebrow}>
                    {currentPrompt?.phase?.replaceAll("-", " ") ?? session.current_phase}
                  </span>
                  <h2>{currentPrompt?.content ?? "Interview prompt is loading."}</h2>
                </div>

                <div className={styles.history}>
                  {(session.messages ?? [])
                    .filter((message) => message.role === "candidate")
                    .map((message) => (
                      <article key={message.id}>
                        <span>{message.phase.replaceAll("-", " ")}</span>
                        <p>{message.content}</p>
                        {typeof message.evidence.score === "number" && (
                          <strong>
                            Phase score {Math.round(message.evidence.score * 100)}
                          </strong>
                        )}
                      </article>
                    ))}
                </div>

                {session.status === "IN_PROGRESS" ? (
                  <div className={styles.answerBox}>
                    <textarea
                      maxLength={50_000}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="Answer as if you were speaking to the interviewer. State assumptions, trade-offs, evidence, and decisions clearly."
                      value={answer}
                    />
                    <button
                      className={styles.primary}
                      disabled={!answer.trim() || Boolean(busy)}
                      onClick={() => void submitAnswer()}
                      type="button"
                    >
                      {busy === "answer" ? (
                        <LoaderCircle className={styles.spin} size={16} />
                      ) : (
                        <Send size={16} />
                      )}
                      Submit response
                    </button>
                  </div>
                ) : (
                  <div className={styles.paused}>
                    {session.status === "PAUSED"
                      ? "This interview is paused. Resume it from the session rail."
                      : "This interview has been cancelled."}
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      )}

      {error && <div className={styles.error}>{error}</div>}
    </section>
  );
}
