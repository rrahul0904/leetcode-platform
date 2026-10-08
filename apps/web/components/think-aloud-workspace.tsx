"use client";

import {
  BrainCircuit,
  CheckCircle2,
  CirclePause,
  CirclePlay,
  Database,
  GitBranch,
  LoaderCircle,
  Mic,
  MicOff,
  Network,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  commitThinkAloudTurn,
  createThinkAloudSession,
  getThinkAloudSession,
  mutateThinkAloudCanvas,
  recordThinkAloudEvent,
  resumeThinkAloudCoaching,
  startThinkAloudCoaching,
  type ThinkAloudMode,
  type ThinkAloudSession,
} from "@/lib/think-aloud-api";

import styles from "./think-aloud-workspace.module.css";

type SpeechRecognitionAlternativeLike = { transcript: string };
type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
};
type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionConstructorLike = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructorLike;
    webkitSpeechRecognition?: SpeechRecognitionConstructorLike;
  }
}

const FOCUSES = [
  {
    slug: "system-design",
    label: "System design",
    description: "Requirements, capacity, architecture, failure modes, and operations.",
  },
  {
    slug: "data-engineering",
    label: "Data engineering",
    description: "Pipelines, storage, reliability, scale, and platform trade-offs.",
  },
  {
    slug: "ai-architecture",
    label: "AI architecture",
    description: "Evaluation, retrieval, safety, cost, and production AI architecture.",
  },
] as const;

function randomKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function eventValue(
  payload: Record<string, unknown>,
  key: string,
  fallback = "",
) {
  const value = payload[key];
  return typeof value === "string" ? value : fallback;
}

export function ThinkAloudWorkspace() {
  const [focus, setFocus] = useState("system-design");
  const [targetRole, setTargetRole] = useState("Staff Software Engineer");
  const [mode, setMode] = useState<ThinkAloudMode>("practice");
  const [experience, setExperience] = useState<ThinkAloudSession | null>(null);
  const [answer, setAnswer] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [coachQuestion, setCoachQuestion] = useState("");
  const [canvasLabel, setCanvasLabel] = useState("");
  const [canvasType, setCanvasType] = useState("service");
  const [busy, setBusy] = useState<
    "create" | "turn" | "event" | "canvas" | "coach" | "resume" | "refresh" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [voiceUnavailable, setVoiceUnavailable] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const session = experience?.session ?? null;
  const control = experience?.control ?? null;
  const currentPrompt = useMemo(
    () =>
      [...(session?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "interviewer") ?? null,
    [session?.messages],
  );
  const latestCoach = useMemo(
    () =>
      [...(session?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "coach") ?? null,
    [session?.messages],
  );
  const candidateTurns = useMemo(
    () => (session?.messages ?? []).filter((message) => message.role === "candidate"),
    [session?.messages],
  );
  const canCommit =
    Boolean(answer.trim()) &&
    session?.status === "IN_PROGRESS" &&
    control?.floor_owner === "candidate" &&
    !busy;

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  async function startInterview() {
    if (!targetRole.trim() || busy) return;
    setBusy("create");
    setError(null);
    setNotice(null);
    try {
      const created = await createThinkAloudSession(
        focus,
        targetRole.trim(),
        mode,
        randomKey("think-create"),
      );
      setExperience(created);
      setAnswer("");
      setInterimTranscript("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Think Aloud could not start.");
    } finally {
      setBusy(null);
    }
  }

  async function refresh() {
    if (!session || busy) return;
    setBusy("refresh");
    setError(null);
    try {
      setExperience(await getThinkAloudSession(session.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Interview could not refresh.");
    } finally {
      setBusy(null);
    }
  }

  async function commitTurn() {
    if (!session || !canCommit) return;
    recognitionRef.current?.stop();
    setListening(false);
    setBusy("turn");
    setError(null);
    setNotice("Turn committed. The interviewer is processing your response.");
    try {
      const updated = await commitThinkAloudTurn(
        session.id,
        answer.trim(),
        randomKey("think-turn"),
      );
      setExperience(updated);
      setAnswer("");
      setInterimTranscript("");
      setNotice(
        updated.session.status === "COMPLETED"
          ? "Interview complete. Your evidence-backed report is ready."
          : "Your turn again. Silence will not advance the interview.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Turn could not be committed.");
    } finally {
      setBusy(null);
    }
  }

  async function recordThinking() {
    if (!session || !control || busy || control.floor_owner !== "candidate") return;
    setBusy("event");
    setError(null);
    try {
      const updated = await recordThinkAloudEvent(
        session.id,
        "candidate_silence",
        { source: "candidate_thinking_control" },
        randomKey("think-silence"),
      );
      setExperience(updated);
      setNotice("Thinking time recorded. You still own the floor.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Thinking state could not be recorded.");
    } finally {
      setBusy(null);
    }
  }

  async function addCanvasComponent() {
    if (!session || !canvasLabel.trim() || busy) return;
    setBusy("canvas");
    setError(null);
    try {
      const updated = await mutateThinkAloudCanvas(
        session.id,
        {
          kind: canvasType === "note" ? "note" : "add_component",
          label: canvasLabel.trim(),
          component_type: canvasType === "note" ? null : canvasType,
          payload: { source: "think_aloud_workspace" },
        },
        randomKey("think-canvas"),
      );
      setExperience(updated);
      setCanvasLabel("");
      setNotice("Architecture canvas saved to the interview evidence stream.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Canvas could not be updated.");
    } finally {
      setBusy(null);
    }
  }

  async function startCoaching() {
    if (!session || busy || control?.mode !== "practice") return;
    setBusy("coach");
    setError(null);
    try {
      const updated = await startThinkAloudCoaching(
        session.id,
        coachQuestion.trim() || null,
        randomKey("think-coach"),
      );
      setExperience(updated);
      setCoachQuestion("");
      setNotice("Interview paused. Coaching is isolated from scored candidate turns.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Coaching could not start.");
    } finally {
      setBusy(null);
    }
  }

  async function resumeCoaching() {
    if (!session || busy) return;
    setBusy("resume");
    setError(null);
    try {
      const updated = await resumeThinkAloudCoaching(
        session.id,
        randomKey("think-resume"),
      );
      setExperience(updated);
      setNotice("Interview resumed. You own the floor again.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Interview could not resume.");
    } finally {
      setBusy(null);
    }
  }

  async function markProviderState(connected: boolean) {
    if (!session) return;
    try {
      const updated = await recordThinkAloudEvent(
        session.id,
        connected ? "provider_reconnected" : "provider_disconnected",
        { provider: "browser_speech_recognition" },
        randomKey(connected ? "think-reconnect" : "think-disconnect"),
      );
      setExperience(updated);
    } catch {
      // Voice-provider telemetry must never erase or block an interview turn.
    }
  }

  function startVoice() {
    if (!session || session.status !== "IN_PROGRESS" || control?.floor_owner !== "candidate") {
      return;
    }
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceUnavailable(true);
      setNotice("Browser voice transcription is unavailable here. Text entry remains fully supported.");
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result?.[0]?.transcript ?? "";
        if (result?.isFinal) finalText += transcript;
        else interimText += transcript;
      }
      if (finalText.trim()) {
        setAnswer((value) => `${value}${value.trim() ? " " : ""}${finalText.trim()}`);
      }
      setInterimTranscript(interimText.trim());
    };
    recognition.onerror = () => {
      setListening(false);
      void markProviderState(false);
      setNotice("Voice capture disconnected. Your transcript and canvas remain saved.");
    };
    recognition.onend = () => {
      setListening(false);
      setInterimTranscript("");
    };
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
    setVoiceUnavailable(false);
    if (control && !control.provider_connected) void markProviderState(true);
  }

  function stopVoice() {
    recognitionRef.current?.stop();
    setListening(false);
    setInterimTranscript("");
  }

  if (!experience) {
    return (
      <section className={styles.shell}>
        <header className={styles.hero}>
          <div>
            <span className={styles.eyebrow}>
              <BrainCircuit size={15} /> THINK ALOUD INTERVIEWS
            </span>
            <h1>Practice system design like a real conversation.</h1>
            <p>
              Speak or type through an interview, build the architecture as you go, pause for
              coaching in practice mode, and finish with evidence tied to what you actually said.
            </p>
          </div>
          <div className={styles.trustCard}>
            <ShieldCheck size={19} />
            <div>
              <strong>You control the floor</strong>
              <span>Silence never means “done.” Only an explicit turn commit advances the interview.</span>
            </div>
          </div>
        </header>

        <div className={styles.setupGrid}>
          <div className={styles.focusCards}>
            <span className={styles.sectionLabel}>Choose an interview</span>
            {FOCUSES.map((item) => (
              <button
                className={item.slug === focus ? styles.focusActive : styles.focusCard}
                key={item.slug}
                onClick={() => setFocus(item.slug)}
                type="button"
              >
                <Network size={18} />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
              </button>
            ))}
          </div>

          <div className={styles.setupPanel}>
            <span className={styles.sectionLabel}>Session configuration</span>
            <label>
              <span>Target role</span>
              <input
                maxLength={160}
                onChange={(event) => setTargetRole(event.target.value)}
                value={targetRole}
              />
            </label>

            <div className={styles.modeToggle} aria-label="Interview mode">
              <button
                className={mode === "practice" ? styles.modeActive : ""}
                onClick={() => setMode("practice")}
                type="button"
              >
                <Sparkles size={15} /> Practice
                <small>Coaching available</small>
              </button>
              <button
                className={mode === "assessment" ? styles.modeActive : ""}
                onClick={() => setMode("assessment")}
                type="button"
              >
                <ShieldCheck size={15} /> Assessment
                <small>No hints or coaching</small>
              </button>
            </div>

            <div className={styles.contracts}>
              <span><CheckCircle2 size={14} /> Explicit turn ownership</span>
              <span><CheckCircle2 size={14} /> Durable architecture canvas</span>
              <span><CheckCircle2 size={14} /> Evidence-backed scoring</span>
              <span><CheckCircle2 size={14} /> Disconnect-safe recovery state</span>
            </div>

            <button
              className={styles.primary}
              disabled={!targetRole.trim() || Boolean(busy)}
              onClick={() => void startInterview()}
              type="button"
            >
              {busy === "create" ? <LoaderCircle className={styles.spin} size={17} /> : <CirclePlay size={17} />}
              Start Think Aloud interview
            </button>
          </div>
        </div>
        {error && <div className={styles.error}>{error}</div>}
      </section>
    );
  }

  const isComplete = session?.status === "COMPLETED";
  const canvas = control?.canvas ?? [];

  return (
    <section className={styles.shell}>
      <header className={styles.sessionHeader}>
        <div>
          <span className={styles.eyebrow}>THINK ALOUD · {control?.mode.toUpperCase()}</span>
          <h1>{session?.focus_label}</h1>
          <p>{session?.target_role}</p>
        </div>
        <div className={styles.sessionStatus}>
          <span className={styles.statusPill}>{statusLabel(session?.status ?? "")}</span>
          <span className={styles.floorPill}>Floor: {control?.floor_owner}</span>
          <span className={control?.provider_connected ? styles.connected : styles.disconnected}>
            {control?.provider_connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {control?.provider_connected ? "Voice ready" : "Voice disconnected"}
          </span>
          <button aria-label="Refresh interview" onClick={() => void refresh()} type="button">
            <RefreshCw className={busy === "refresh" ? styles.spin : ""} size={15} />
          </button>
        </div>
      </header>

      {isComplete && session?.report ? (
        <section className={styles.report}>
          <span className={styles.eyebrow}>ASSESSMENT COMPLETE</span>
          <div className={styles.reportTop}>
            <div className={styles.scoreRing}>
              <strong>{Math.round(session.report.overall_score * 100)}</strong>
              <span>/100</span>
            </div>
            <div>
              <h2>Evidence-backed interview report</h2>
              <p>
                The completed session is finalized. Transcript, canvas events, and the generated
                report can be replayed, but the interview evidence can no longer be mutated.
              </p>
            </div>
          </div>
          <div className={styles.reportColumns}>
            <div>
              <span>Strengths</span>
              {session.report.strengths.map((item) => <p key={item}>{item}</p>)}
            </div>
            <div>
              <span>Growth areas</span>
              {session.report.growth_areas.map((item) => <p key={item}>{item}</p>)}
            </div>
            <div>
              <span>Next steps</span>
              {session.report.next_steps.map((item) => <p key={item}>{item}</p>)}
            </div>
          </div>
          <div className={styles.finalEvidence}>
            <strong>{candidateTurns.length} candidate turns</strong>
            <strong>{canvas.length} canvas events</strong>
            <strong>{session.report.rubric_evidence.length} scored phases</strong>
          </div>
          <button className={styles.primary} onClick={() => setExperience(null)} type="button">
            Start another interview
          </button>
        </section>
      ) : (
        <div className={styles.workspace}>
          <main className={styles.conversationPanel}>
            <div className={styles.promptCard}>
              <span className={styles.eyebrow}>{currentPrompt?.phase?.replaceAll("-", " ")}</span>
              <h2>{currentPrompt?.content ?? "Loading the next interview prompt…"}</h2>
              <p>
                Take your time. Pauses do not surrender your turn. Commit only when you are ready
                for the interviewer to advance.
              </p>
            </div>

            <div className={styles.transcript}>
              {candidateTurns.length === 0 ? (
                <div className={styles.emptyTranscript}>Your committed responses will appear here.</div>
              ) : (
                candidateTurns.map((message) => (
                  <article key={message.id}>
                    <span>{message.phase.replaceAll("-", " ")}</span>
                    <p>{message.content}</p>
                    {typeof message.evidence.score === "number" && (
                      <strong>{Math.round(message.evidence.score * 100)} phase evidence</strong>
                    )}
                  </article>
                ))
              )}
            </div>

            {control?.coaching_active ? (
              <section className={styles.coachCard}>
                <span><Sparkles size={15} /> COACHING PAUSE</span>
                <h3>{latestCoach?.content ?? "Coaching guidance is ready."}</h3>
                <button className={styles.primary} disabled={Boolean(busy)} onClick={() => void resumeCoaching()} type="button">
                  {busy === "resume" ? <LoaderCircle className={styles.spin} size={16} /> : <CirclePlay size={16} />}
                  Resume interview
                </button>
              </section>
            ) : (
              <div className={styles.answerComposer}>
                <textarea
                  aria-label="Candidate response"
                  maxLength={50_000}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="Speak or type your reasoning. Clarify assumptions, make decisions, explain trade-offs, and test failure modes."
                  value={answer}
                />
                {interimTranscript && <div className={styles.interim}>{interimTranscript}</div>}
                <div className={styles.composerActions}>
                  {listening ? (
                    <button className={styles.voiceLive} onClick={stopVoice} type="button">
                      <MicOff size={15} /> Stop mic
                    </button>
                  ) : (
                    <button onClick={startVoice} type="button">
                      <Mic size={15} /> Speak
                    </button>
                  )}
                  <button disabled={Boolean(busy)} onClick={() => void recordThinking()} type="button">
                    <BrainCircuit size={15} /> I’m thinking
                  </button>
                  <button className={styles.primary} disabled={!canCommit} onClick={() => void commitTurn()} type="button">
                    {busy === "turn" ? <LoaderCircle className={styles.spin} size={16} /> : <Send size={16} />}
                    Done speaking
                  </button>
                </div>
                {voiceUnavailable && (
                  <small className={styles.voiceNote}>Voice transcription is not exposed by this browser; the same interview works with text.</small>
                )}
              </div>
            )}

            {notice && <div className={styles.notice}>{notice}</div>}
            {error && <div className={styles.error}>{error}</div>}
          </main>

          <aside className={styles.sidePanel}>
            <section className={styles.canvasPanel}>
              <div className={styles.panelHeading}>
                <span><GitBranch size={15} /> Architecture canvas</span>
                <small>{canvas.length} events</small>
              </div>
              <div className={styles.canvasItems}>
                {canvas.length === 0 ? (
                  <div className={styles.emptyCanvas}>Add services, queues, stores, or design notes as you talk.</div>
                ) : (
                  canvas.map((item) => (
                    <div className={styles.canvasItem} key={item.sequence_number}>
                      <Database size={15} />
                      <span>
                        <strong>{item.content}</strong>
                        <small>{eventValue(item.payload, "component_type", eventValue(item.payload, "kind", "canvas"))}</small>
                      </span>
                    </div>
                  ))
                )}
              </div>
              <div className={styles.canvasComposer}>
                <select aria-label="Canvas component type" onChange={(event) => setCanvasType(event.target.value)} value={canvasType}>
                  <option value="service">Service</option>
                  <option value="queue">Queue</option>
                  <option value="database">Database</option>
                  <option value="cache">Cache</option>
                  <option value="client">Client</option>
                  <option value="external">External provider</option>
                  <option value="note">Design note</option>
                </select>
                <input
                  aria-label="Canvas component label"
                  maxLength={180}
                  onChange={(event) => setCanvasLabel(event.target.value)}
                  placeholder="e.g. Notification API"
                  value={canvasLabel}
                />
                <button disabled={!canvasLabel.trim() || Boolean(busy)} onClick={() => void addCanvasComponent()} type="button">
                  {busy === "canvas" ? <LoaderCircle className={styles.spin} size={15} /> : <Plus size={15} />}
                  Add to canvas
                </button>
              </div>
            </section>

            <section className={styles.coachingPanel}>
              <div className={styles.panelHeading}>
                <span><Sparkles size={15} /> Coach</span>
                <small>{control?.mode === "practice" ? "Practice only" : "Locked"}</small>
              </div>
              {control?.mode === "assessment" ? (
                <div className={styles.assessmentLock}>
                  <ShieldCheck size={18} />
                  <strong>Assessment isolation</strong>
                  <p>Hints and coaching are disabled so the scored evidence remains unassisted.</p>
                </div>
              ) : (
                <>
                  <textarea
                    aria-label="Coaching question"
                    maxLength={2_000}
                    onChange={(event) => setCoachQuestion(event.target.value)}
                    placeholder="Optional: ask the coach what to focus on before resuming."
                    value={coachQuestion}
                  />
                  <button
                    disabled={Boolean(busy) || session?.status !== "IN_PROGRESS"}
                    onClick={() => void startCoaching()}
                    type="button"
                  >
                    {busy === "coach" ? <LoaderCircle className={styles.spin} size={15} /> : <CirclePause size={15} />}
                    Pause for coaching
                  </button>
                </>
              )}
            </section>
          </aside>
        </div>
      )}
    </section>
  );
}
