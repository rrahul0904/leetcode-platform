"use client";

import {
  BrainCircuit,
  LoaderCircle,
  MessageCircle,
  Plus,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  createTutorSession,
  endTutorSession,
  listTutorEvents,
  listTutorSessions,
  sendTutorMessage,
  type CandidateLevel,
  type TutorEvent,
  type TutorSession,
} from "@/lib/tutor-api";

import styles from "./tutor-dock.module.css";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  meta?: string;
};

const QUICK_PROMPTS = [
  "Give me a hint",
  "Review my approach",
  "What edge case am I missing?",
  "What is my complexity?",
] as const;

const LEVEL_LABELS: Record<CandidateLevel, string> = {
  junior: "Junior",
  mid: "Mid-level",
  senior: "Senior",
  staff: "Staff+",
  manager: "Manager",
};

function eventMessages(events: TutorEvent[]): ChatMessage[] {
  return events.flatMap((event) => {
    const text = event.payload.message;
    if (typeof text !== "string") return [];
    if (event.event_type === "message.user") {
      return [{ id: event.id, role: "user" as const, text }];
    }
    if (event.event_type === "message.assistant") {
      const provider =
        typeof event.payload.provider === "string" ? event.payload.provider : "tutor";
      const model = typeof event.payload.model === "string" ? event.payload.model : "";
      return [
        {
          id: event.id,
          role: "assistant" as const,
          text,
          meta: [provider, model].filter(Boolean).join(" · "),
        },
      ];
    }
    return [];
  });
}

export function TutorDock({ slug }: { slug: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [session, setSession] = useState<TutorSession | null>(null);
  const [level, setLevel] = useState<CandidateLevel>("mid");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  const sessionLabel = useMemo(
    () => (session ? `${LEVEL_LABELS[session.candidate_level]} · code-aware` : "Code-aware"),
    [session],
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    void listTutorSessions(controller.signal)
      .then(async (sessions) => {
        const active = sessions.find(
          (candidate) =>
            candidate.status === "active" &&
            candidate.question_slug === slug &&
            candidate.mode === "practice" &&
            candidate.surface === "code",
        );
        if (!active) return;
        setSession(active);
        setLevel(active.candidate_level);
        const events = await listTutorEvents(active.id, controller.signal);
        setMessages(eventMessages(events));
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Tutor history is unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [slug]);

  useEffect(() => {
    if (!open) return;
    messagesRef.current?.scrollTo({
      top: messagesRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, open, sending]);

  async function ensureSession(): Promise<TutorSession> {
    if (session) return session;
    const created = await createTutorSession({ questionSlug: slug, candidateLevel: level });
    setSession(created);
    return created;
  }

  async function submitMessage(value: string) {
    const message = value.trim();
    if (!message || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    const optimisticId = `optimistic-${crypto.randomUUID()}`;
    setMessages((current) => [
      ...current,
      { id: optimisticId, role: "user", text: message },
    ]);
    try {
      const active = await ensureSession();
      const response = await sendTutorMessage(
        active.id,
        message,
        `web-${crypto.randomUUID()}`,
      );
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${crypto.randomUUID()}`,
          role: "assistant",
          text: response.reply,
          meta: `${response.provider} · ${response.model}`,
        },
      ]);
    } catch (reason) {
      setMessages((current) => current.filter((item) => item.id !== optimisticId));
      setDraft(message);
      setError(reason instanceof Error ? reason.message : "The tutor could not respond.");
    } finally {
      setSending(false);
    }
  }

  async function startFreshSession() {
    if (sending) return;
    setError(null);
    try {
      if (session?.status === "active") await endTutorSession(session.id);
      setSession(null);
      setMessages([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not reset the tutor session.");
    }
  }

  if (!open) {
    return (
      <button
        aria-label="Open AI tutor"
        className={styles.launcher}
        onClick={() => setOpen(true)}
        type="button"
      >
        <Sparkles size={18} /> AI Tutor
      </button>
    );
  }

  return (
    <aside aria-label="AI coding tutor" className={styles.panel}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <span className={styles.avatar}>
            <BrainCircuit size={20} />
          </span>
          <div className={styles.identityText}>
            <strong>SkillForge Tutor</strong>
            <span>{sessionLabel}</span>
          </div>
        </div>
        <div className={styles.headerActions}>
          <button
            aria-label="Start a new tutor session"
            className={styles.iconButton}
            disabled={sending}
            onClick={() => void startFreshSession()}
            title="New tutor session"
            type="button"
          >
            <Plus size={17} />
          </button>
          <button
            aria-label="Close AI tutor"
            className={styles.iconButton}
            onClick={() => setOpen(false)}
            type="button"
          >
            <X size={18} />
          </button>
        </div>
      </header>

      <div className={styles.controls}>
        <span className={styles.status}>
          <span className={styles.statusDot} /> Watching your saved draft
        </span>
        <select
          aria-label="Tutor seniority"
          disabled={Boolean(session)}
          onChange={(event) => setLevel(event.target.value as CandidateLevel)}
          value={session?.candidate_level ?? level}
        >
          {Object.entries(LEVEL_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.messages} ref={messagesRef}>
        {loading ? (
          <div className={styles.welcome}>
            <LoaderCircle className="spin" size={21} />
            <p>Restoring your tutor session…</p>
          </div>
        ) : messages.length === 0 ? (
          <div className={styles.welcome}>
            <span className={styles.welcomeIcon}>
              <MessageCircle size={22} />
            </span>
            <h3>Think with a coach, not an answer bot.</h3>
            <p>
              I can see the draft SkillsForge has safely autosaved for this problem. Ask
              for a hint, debugging help, edge cases, or a complexity check.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              className={`${styles.message} ${
                message.role === "user" ? styles.userMessage : styles.assistantMessage
              }`}
              key={message.id}
            >
              {message.text}
              {message.meta && <span className={styles.meta}>{message.meta}</span>}
            </div>
          ))
        )}
        {sending && (
          <div className={`${styles.message} ${styles.assistantMessage}`}>
            <LoaderCircle className="spin" size={15} /> Thinking about your current draft…
          </div>
        )}
      </div>

      <div className={styles.quickPrompts}>
        {QUICK_PROMPTS.map((prompt) => (
          <button
            disabled={sending}
            key={prompt}
            onClick={() => void submitMessage(prompt)}
            type="button"
          >
            {prompt}
          </button>
        ))}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.composer}>
        <div className={styles.inputShell}>
          <textarea
            aria-label="Message AI tutor"
            disabled={sending}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submitMessage(draft);
              }
            }}
            placeholder="Ask about your approach…"
            rows={1}
            value={draft}
          />
          <button
            aria-label="Send message"
            className={styles.sendButton}
            disabled={sending || !draft.trim()}
            onClick={() => void submitMessage(draft)}
            type="button"
          >
            {sending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}
          </button>
        </div>
        <div className={styles.disclaimer}>
          Uses public problem data and your candidate-owned draft. Hidden tests stay private.
        </div>
      </div>
    </aside>
  );
}
