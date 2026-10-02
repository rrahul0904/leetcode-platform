"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FALLING_WORDS, WORD_SET_PROVENANCE } from "@/lib/falling-words/words";
import { GameEngine, type GameSnapshot, type RunResult } from "@/lib/falling-words/game-engine";

import styles from "./typing-arcade.module.css";

const HISTORY_KEY = "rigor.typing-arcade.history.v1";
const SETTINGS_KEY = "rigor.typing-arcade.settings.v1";
const MAX_HISTORY = 30;
const BOARD_WIDTH = 64;
const BOARD_HEIGHT = 13;

function readHistory(): RunResult[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) {
      window.localStorage.removeItem(HISTORY_KEY);
      return [];
    }
    const entries = value.filter((item): item is RunResult => {
      if (!item || typeof item !== "object") return false;
      const row = item as Partial<RunResult>;
      return Number.isSafeInteger(row.runId) && row.runId! > 0 &&
        (row.reason === "won" || row.reason === "lost" || row.reason === "exited") &&
        Number.isSafeInteger(row.score) && row.score! >= 0 &&
        Number.isSafeInteger(row.level) && row.level! >= 1 &&
        Number.isSafeInteger(row.lives) && row.lives! >= 0 &&
        Number.isSafeInteger(row.matchedWords) && row.matchedWords! >= 0 &&
        Number.isSafeInteger(row.missedWords) && row.missedWords! >= 0 &&
        Number.isFinite(row.activeElapsedMs) && row.activeElapsedMs! >= 0 &&
        Number.isFinite(row.startedAtMs) && row.startedAtMs! >= 0 &&
        Number.isFinite(row.finishedAtMs) && row.finishedAtMs! >= row.startedAtMs!;
    }).slice(0, MAX_HISTORY);
    if (value.length > 0 && entries.length === 0) window.localStorage.removeItem(HISTORY_KEY);
    return entries;
  } catch {
    try { window.localStorage.removeItem(HISTORY_KEY); } catch { /* storage is disabled */ }
    return [];
  }
}

function readStartingLives(): 1 | 3 | 5 {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "null");
    if (value && typeof value === "object" && "schemaVersion" in value &&
        value.schemaVersion === 1 && "startingLives" in value &&
        (value.startingLives === 1 || value.startingLives === 3 || value.startingLives === 5)) {
      return value.startingLives;
    }
    if (value !== null) window.localStorage.removeItem(SETTINGS_KEY);
  } catch {
    try { window.localStorage.removeItem(SETTINGS_KEY); } catch { /* storage is disabled */ }
  }
  return 3;
}

function initialSnapshot(): GameSnapshot {
  return new GameEngine(
    { width: BOARD_WIDTH, height: BOARD_HEIGHT, words: FALLING_WORDS },
    { now: Date.now, random: Math.random },
  ).snapshot;
}

export function TypingArcade() {
  const engine = useMemo(
    () => new GameEngine(
      { width: BOARD_WIDTH, height: BOARD_HEIGHT, words: FALLING_WORDS },
      { now: Date.now, random: Math.random },
    ),
    [],
  );
  const [game, setGame] = useState<GameSnapshot>(initialSnapshot);
  const [answer, setAnswer] = useState("");
  const [history, setHistory] = useState<RunResult[]>([]);
  const [startingLives, setStartingLives] = useState<1 | 3 | 5>(3);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastSavedRun = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        setHistory(readHistory());
        const lives = readStartingLives();
        engine.setStartingLives(lives);
        setStartingLives(lives);
        setGame(engine.snapshot);
      }
    });
    return () => { active = false; };
  }, [engine]);

  const refresh = useCallback(() => setGame(engine.snapshot), [engine]);

  const begin = useCallback(() => {
    if (engine.snapshot.state === "menu") engine.prepare();
    if (engine.snapshot.state === "won" || engine.snapshot.state === "lost" || engine.snapshot.state === "exited") {
      engine.restart();
    }
    engine.start();
    setAnswer("");
    refresh();
    queueMicrotask(() => inputRef.current?.focus());
  }, [engine, refresh]);

  const restart = useCallback(() => {
    engine.restart();
    engine.start();
    setAnswer("");
    refresh();
    queueMicrotask(() => inputRef.current?.focus());
  }, [engine, refresh]);

  const togglePause = useCallback(() => {
    if (engine.snapshot.state === "playing") engine.pause();
    else engine.resume();
    refresh();
    if (engine.snapshot.state === "playing") queueMicrotask(() => inputRef.current?.focus());
  }, [engine, refresh]);

  useEffect(() => {
    if (game.state !== "playing") return;
    let previous = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const delta = Math.max(0, Math.min(1000, now - previous));
      previous = now;
      engine.tick(delta);
      refresh();
    }, 100);
    return () => window.clearInterval(timer);
  }, [engine, game.state, refresh]);

  useEffect(() => {
    if (game.state !== "playing") return;
    const pauseOnFocusLoss = () => {
      if (document.hidden || !document.hasFocus()) {
        engine.pause();
        refresh();
      }
    };
    document.addEventListener("visibilitychange", pauseOnFocusLoss);
    window.addEventListener("blur", pauseOnFocusLoss);
    return () => {
      document.removeEventListener("visibilitychange", pauseOnFocusLoss);
      window.removeEventListener("blur", pauseOnFocusLoss);
    };
  }, [engine, game.state, refresh]);

  useEffect(() => {
    const result = game.lastResult;
    if (!result || result.runId === lastSavedRun.current) return;
    lastSavedRun.current = result.runId;
    const next = [result, ...readHistory()].filter((row, index, rows) =>
      rows.findIndex((candidate) =>
        candidate.runId === row.runId && candidate.startedAtMs === row.startedAtMs,
      ) === index,
    ).slice(0, MAX_HISTORY);
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      queueMicrotask(() => setHistory(next));
    } catch {
      // A storage quota or privacy setting must not interrupt the run result.
      queueMicrotask(() => setHistory((current) => [result, ...current].slice(0, MAX_HISTORY)));
    }
  }, [game.lastResult]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (engine.submit(answer) !== null) setAnswer("");
    refresh();
  }

  function clearHistory() {
    try {
      window.localStorage.removeItem(HISTORY_KEY);
    } catch {
      // Keep the visible reset available even if storage is disabled.
    }
    setHistory([]);
  }

  function updateStartingLives(value: string) {
    const lives = Number(value);
    if (lives !== 1 && lives !== 3 && lives !== 5) return;
    if (!engine.setStartingLives(lives)) return;
    setStartingLives(lives);
    refresh();
    try {
      window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ schemaVersion: 1, startingLives: lives }));
    } catch {
      // The current setting still applies to this run when storage is unavailable.
    }
  }

  function resetSettings() {
    updateStartingLives("3");
    try {
      window.localStorage.removeItem(SETTINGS_KEY);
    } catch {
      // Keep the in-memory default even if device storage is blocked.
    }
  }

  const active = game.state === "playing";
  const terminal = game.state === "won" || game.state === "lost";
  const status = game.state === "menu" || game.state === "ready"
    ? "Ready to start"
    : game.state === "playing"
      ? "Game in progress"
      : game.state === "paused"
        ? "Paused"
        : game.state === "won"
          ? "You won"
          : game.state === "lost"
            ? "Game over"
            : "Run ended";

  return (
    <main className={styles.page}>
      <header className={styles.intro}>
        <div>
          <span className={styles.eyebrow}>PRACTICE · TYPING ARCADE</span>
          <h1>Falling Words</h1>
          <p>Type a visible word and press Enter before it reaches the bottom. Each match earns points; reaching level 27 wins the run.</p>
        </div>
      </header>
      <section aria-label="Falling Words game">
        <div className={styles.controls}>
          {!active && game.state !== "paused" && !terminal && <button onClick={begin} type="button">Start game</button>}
          {active && <button onClick={togglePause} type="button">Pause</button>}
          {game.state === "paused" && <button onClick={togglePause} type="button">Resume</button>}
          {(active || game.state === "paused" || terminal) && <button onClick={restart} type="button">Restart</button>}
          <label>Lives
            <select aria-label="Starting lives" value={startingLives} onChange={(event) => updateStartingLives(event.target.value)} disabled={active || game.state === "paused"}>
              <option value="1">1 · Challenge</option>
              <option value="3">3 · Standard</option>
              <option value="5">5 · Relaxed</option>
            </select>
          </label>
          <div className={styles.hud} aria-label="Game statistics" aria-live="polite">
            <div className={styles.stat}><span>Score</span><strong>{game.score}</strong></div>
            <div className={styles.stat}><span>Level</span><strong>{game.level}</strong></div>
            <div className={styles.stat}><span>Lives</span><strong>{game.lives}</strong></div>
            <div className={styles.stat}><span>Matched</span><strong>{game.matchedWords}</strong></div>
          </div>
        </div>
        <div className={styles.board} role="region" aria-label={`Falling word board. ${status}.`} aria-live="off">
          {game.words.map((word) => (
            <span
              className={styles.word}
              key={word.id}
              style={{ left: `${(word.x / BOARD_WIDTH) * 100}%`, top: `${(word.y / BOARD_HEIGHT) * 100}%` }}
            >
              {word.text}
            </span>
          ))}
          {game.words.length === 0 && <div className={styles.emptyBoard}>{status}{game.state === "menu" ? ". Choose Start game when you are ready." : game.state === "paused" ? ". Resume when you are ready." : " — new words will appear shortly."}</div>}
        </div>
        <form className={styles.entry} onSubmit={submit}>
          <label className="sr-only" htmlFor="falling-word-answer">Type a visible word</label>
          <input ref={inputRef} autoComplete="off" autoCapitalize="off" spellCheck={false} id="falling-word-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} disabled={!active} placeholder={active ? "Type a word…" : "Start or resume to type"} />
          <button disabled={!active || !answer} type="submit">Match</button>
        </form>
        <p className={styles.hint}>Matches are exact and case-sensitive. Spaces inside a phrase count. Unmatched words stay in the entry field. The game pauses when this tab loses focus.</p>
      </section>
      {terminal && game.lastResult && (
        <section className={styles.result} aria-live="polite" aria-labelledby="run-result-title">
          <h2 id="run-result-title">{game.state === "won" ? "Run complete" : "Run ended"}</h2>
          <p>Score {game.lastResult.score} · level {game.lastResult.level} · {game.lastResult.matchedWords} matched · {game.lastResult.missedWords} missed.</p>
        </section>
      )}
      <section className={styles.history} aria-labelledby="arcade-history-title">
        <div className={styles.historyHeader}>
          <div><h2 id="arcade-history-title">On this device</h2><span className={styles.hint}>Run history stays in this browser.</span></div>
          <button className={styles.clearButton} onClick={clearHistory} type="button" disabled={history.length === 0}>Clear history</button>
          <button className={styles.clearButton} onClick={resetSettings} type="button" disabled={startingLives === 3}>Reset settings</button>
        </div>
        {history.length > 0 ? <ol>{history.map((item) => <li key={`${item.runId}-${item.finishedAtMs}`}>{item.reason} · {item.score} pts · level {item.level}</li>)}</ol> : <p className={styles.hint}>Completed runs will appear here. {WORD_SET_PROVENANCE}</p>}
      </section>
    </main>
  );
}
