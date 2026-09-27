"use client";

import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { applyText, newSession, sessionMetrics, tick } from "@/lib/code-typing/engine";
import {
  appendHistory, clearHistory, historyEntry, readHistory, type HistoryEntry,
} from "@/lib/code-typing/history";
import {
  DURATIONS, LANGUAGES, snippetLength, snippetsFor, type TypingLanguage,
} from "@/lib/code-typing/snippets";

import styles from "./code-typing-practice.module.css";

function clock(remainingMs: number) {
  const totalSeconds = Math.ceil(Math.max(0, remainingMs) / 1000);
  return `${Math.floor(totalSeconds / 60).toString().padStart(2, "0")}:${(totalSeconds % 60).toString().padStart(2, "0")}`;
}
function round(value: number) {
  return Math.round(value);
}
export function CodeTypingPractice() {
  const [language, setLanguage] = useState<TypingLanguage>("python");
  const [duration, setDuration] = useState<number>(60);
  const [index, setIndex] = useState(0);
  const [session, setSession] = useState(() => newSession(snippetsFor("python")[0], 60));
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [storageWarning, setStorageWarning] = useState("");
  const [attempt, setAttempt] = useState(0);
  const savedAttempt = useRef<number | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const composing = useRef(false);

  useEffect(() => {
    setHistory(readHistory(window.localStorage));
    const syncHistory = () => setHistory(readHistory(window.localStorage));
    window.addEventListener("storage", syncHistory);
    return () => window.removeEventListener("storage", syncHistory);
  }, []);

  useEffect(() => {
    if (session.status !== "active") return;
    const update = () => setSession((current) => tick(current, performance.now()));
    const interval = window.setInterval(update, 100);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", update);
    };
  }, [session.status]);

  useEffect(() => {
    if ((session.status !== "completed" && session.status !== "timed-out") ||
        savedAttempt.current === attempt) return;
    savedAttempt.current = attempt;
    try {
      const id = typeof window.crypto.randomUUID === "function"
        ? window.crypto.randomUUID() : `${Date.now()}-${attempt}-${Math.random()}`;
      setHistory(appendHistory(window.localStorage, historyEntry(session, id, Date.now())));
    } catch {
      setStorageWarning("Local history could not be saved in this browser.");
    }
  }, [session, attempt]);

  function choose(nextLanguage: TypingLanguage, nextDuration: number, nextIndex: number) {
    const options = snippetsFor(nextLanguage);
    setLanguage(nextLanguage);
    setDuration(nextDuration);
    setIndex(nextIndex);
    composing.current = false;
    setSession(newSession(options[nextIndex], nextDuration));
    setAttempt((previous) => previous + 1);
    inputRef.current?.focus();
  }
  function changeText(value: string) {
    setSession((current) => applyText(current, value, performance.now()));
  }
  function onChange(event: ChangeEvent<HTMLTextAreaElement>) {
    if (!composing.current) changeText(event.currentTarget.value);
  }
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Tab" || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    if (session.status !== "idle" && session.status !== "active") return;
    const editor = event.currentTarget;
    const spaces = " ".repeat(session.snippet.indentation);
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const next = session.input.slice(0, start) + spaces + session.input.slice(end);
    changeText(next);
    queueMicrotask(() => inputRef.current?.setSelectionRange(start + spaces.length, start + spaces.length));
  }
  function clearGuestHistory() {
    try {
      clearHistory(window.localStorage);
      setHistory([]);
      setStorageWarning("");
    } catch {
      setStorageWarning("Local history could not be cleared in this browser.");
    }
  }

  const metrics = sessionMetrics(session);
  const terminal = session.status === "completed" || session.status === "timed-out";
  const remainingMs = session.durationMs - session.elapsedMs;
  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Practice / Code typing</p>
        <h1>Build fluency, one character at a time.</h1>
        <p>Transcribe an original teaching example. This is text practice only: your code is never run or graded for behavior.</p>
      </header>
      <section className={styles.panel} aria-label="Code typing setup">
        <div className={styles.controls} role="group" aria-label="Language">
          {LANGUAGES.map((option) => (
            <button key={option} type="button" aria-pressed={language === option}
              onClick={() => choose(option, duration, 0)}>
              {option === "javascript" ? "JavaScript" : option === "sql" ? "SQL" : "Python"}
            </button>
          ))}
        </div>
        <div className={styles.controls} role="group" aria-label="Duration">
          {DURATIONS.map((seconds) => (
            <button key={seconds} type="button" aria-pressed={duration === seconds}
              onClick={() => choose(language, seconds, index)}>{seconds}s</button>
          ))}
        </div>
        <div className={styles.actions}>
          <button type="button" onClick={() => choose(language, duration, (index + 1) % snippetsFor(language).length)}>
            Shuffle example
          </button>
          <button type="button" onClick={() => choose(language, duration, index)}>Restart</button>
        </div>
      </section>
      <section className={styles.panel} aria-label="Typing workspace">
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>{session.snippet.topic} · {session.snippet.difficulty} · v{session.snippet.version}</p>
            <h2>Type the displayed text exactly</h2>
          </div>
          <div className={styles.status} aria-live="polite">
            <strong>{session.status === "timed-out" ? "Time expired" : session.status}</strong>
            <span aria-label="Time remaining">{clock(remainingMs)}</span>
          </div>
        </div>
        <p id="typing-instructions" className={styles.instructions}>
          The clock begins with your first character. Tab inserts {session.snippet.indentation} spaces; Shift+Tab leaves the editor.
          Backspace and selection corrections are allowed. Paste and drop are disabled.
        </p>
        <pre className={styles.example} aria-label="Snippet to type"><code>{session.snippet.expectedText}</code></pre>
        <label className={styles.editorLabel} htmlFor="code-typing-editor">Your transcription</label>
        <textarea
          id="code-typing-editor" ref={inputRef} className={styles.editor}
          aria-label="Type the displayed snippet" aria-describedby="typing-instructions"
          spellCheck={false} autoCapitalize="off" autoCorrect="off" autoComplete="off"
          wrap="off" value={session.input} readOnly={terminal} onChange={onChange} onKeyDown={onKeyDown}
          onCompositionStart={() => { composing.current = true; }}
          onCompositionEnd={(event) => { composing.current = false; changeText(event.currentTarget.value); }}
          onBeforeInput={(event) => {
            const inputType = (event.nativeEvent as InputEvent).inputType;
            if (inputType === "insertFromPaste" || inputType === "insertFromDrop") event.preventDefault();
          }}
          onPaste={(event) => event.preventDefault()}
          onDrop={(event) => event.preventDefault()}
        />
        <p className={styles.instructions}>Aligned: {metrics.correctChars} / {snippetLength(session.snippet)} characters. Errors can be corrected without resetting the clock.</p>
        <div className={styles.metrics} aria-label="Typing metrics">
          <div><span>Net CPM</span><output aria-label="Net CPM">{round(metrics.cpm)}</output></div>
          <div><span>WPM</span><output aria-label="WPM">{round(metrics.wpm)}</output></div>
          <div><span>Accuracy</span><output aria-label="Accuracy">{round(metrics.accuracy)}%</output></div>
          <div><span>Gross CPM</span><output aria-label="Gross CPM">{round(metrics.grossCpm)}</output></div>
        </div>
        {terminal && <p role="status" className={styles.result}>
          {session.status === "completed" ? "Snippet completed." : "Time expired; incomplete attempts are retained."}
          {" "}Use Restart to try this example again.
        </p>}
      </section>
      <section className={styles.panel} aria-label="Guest history">
        <div className={styles.heading}>
          <div><p className={styles.eyebrow}>This browser only</p><h2>Guest history</h2></div>
          <button type="button" disabled={history.length === 0} onClick={clearGuestHistory}>Clear history</button>
        </div>
        {storageWarning && <p role="alert">{storageWarning}</p>}
        {history.length === 0 ? <p>No finished attempts saved in this browser.</p> : (
          <ol className={styles.history}>
            {history.map((entry) => (
              <li key={entry.id}>
                <strong>{entry.language} · {entry.status}</strong>
                <span>{round(entry.cpm)} CPM · {round(entry.wpm)} WPM · {round(entry.accuracy)}%</span>
                <small>Example {entry.snippetId} v{entry.snippetVersion} · {entry.durationSeconds}s</small>
              </li>
            ))}
          </ol>
        )}
        <p className={styles.instructions}>The last 30 finished attempts are stored locally. Input text, identity and results are not sent to a server. Clear history removes this module’s guest results.</p>
      </section>
    </main>
  );
}
