"use client";

import { Pause, Play, RotateCcw, TimerReset } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import styles from "./design-interview-timer.module.css";

type TimerState = {
  durationSeconds: number;
  elapsedSeconds: number;
  running: boolean;
  startedAt: number | null;
};

const STORAGE_KEY = "skillforge-design-interview-timer-v1";
const presets = [30, 45, 60] as const;
const defaultState: TimerState = {
  durationSeconds: 45 * 60,
  elapsedSeconds: 0,
  running: false,
  startedAt: null,
};

function readTimerState(): TimerState {
  if (typeof window === "undefined") {
    return defaultState;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaultState;
    }
    const parsed = JSON.parse(raw) as Partial<TimerState>;
    const durationSeconds =
      typeof parsed.durationSeconds === "number" && parsed.durationSeconds > 0
        ? parsed.durationSeconds
        : defaultState.durationSeconds;
    const elapsedSeconds =
      typeof parsed.elapsedSeconds === "number" && parsed.elapsedSeconds >= 0
        ? parsed.elapsedSeconds
        : 0;
    const running = parsed.running === true;
    const startedAt = typeof parsed.startedAt === "number" ? parsed.startedAt : null;
    if (!running || startedAt === null) {
      return { durationSeconds, elapsedSeconds, running: false, startedAt: null };
    }
    const delta = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    return {
      durationSeconds,
      elapsedSeconds: elapsedSeconds + delta,
      running: true,
      startedAt: Date.now(),
    };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return defaultState;
  }
}

function formatClock(seconds: number) {
  const sign = seconds < 0 ? "-" : "";
  const absolute = Math.abs(seconds);
  const minutes = Math.floor(absolute / 60);
  const remainder = absolute % 60;
  return `${sign}${minutes.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
}

export function DesignInterviewTimer() {
  const [timer, setTimer] = useState<TimerState>(readTimerState);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(timer));
  }, [timer]);

  useEffect(() => {
    if (!timer.running) {
      return;
    }
    const interval = window.setInterval(() => {
      setTimer((current) => ({
        ...current,
        elapsedSeconds: current.elapsedSeconds + 1,
        startedAt: Date.now(),
      }));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [timer.running]);

  const remainingSeconds = timer.durationSeconds - timer.elapsedSeconds;
  const progress = useMemo(
    () => Math.min(100, Math.max(0, (timer.elapsedSeconds / timer.durationSeconds) * 100)),
    [timer.durationSeconds, timer.elapsedSeconds],
  );
  const overtime = remainingSeconds < 0;

  function selectPreset(minutes: (typeof presets)[number]) {
    setTimer({
      durationSeconds: minutes * 60,
      elapsedSeconds: 0,
      running: false,
      startedAt: null,
    });
  }

  function toggleRunning() {
    setTimer((current) => ({
      ...current,
      running: !current.running,
      startedAt: current.running ? null : Date.now(),
    }));
  }

  function reset() {
    setTimer((current) => ({
      ...current,
      elapsedSeconds: 0,
      running: false,
      startedAt: null,
    }));
  }

  return (
    <section aria-label="Design interview timer" className={styles.timer}>
      <div className={styles.summary}>
        <TimerReset size={18} />
        <div>
          <strong>{overtime ? "Overtime" : "Interview clock"}</strong>
          <span>
            {timer.running ? "Running" : timer.elapsedSeconds > 0 ? "Paused" : "Ready"} · {Math.round(progress)}% used
          </span>
        </div>
      </div>

      <output aria-live="polite" className={overtime ? styles.clockOvertime : styles.clock}>
        {formatClock(remainingSeconds)}
      </output>

      <div className={styles.presets} aria-label="Interview duration">
        {presets.map((minutes) => (
          <button
            aria-pressed={timer.durationSeconds === minutes * 60}
            className={timer.durationSeconds === minutes * 60 ? styles.presetActive : styles.preset}
            key={minutes}
            onClick={() => selectPreset(minutes)}
            type="button"
          >
            {minutes} min
          </button>
        ))}
      </div>

      <div className={styles.actions}>
        <button className="button button--dark" onClick={toggleRunning} type="button">
          {timer.running ? <Pause size={14} /> : <Play size={14} />}
          {timer.running ? "Pause" : timer.elapsedSeconds > 0 ? "Resume" : "Start"}
        </button>
        <button className="button button--ghost" onClick={reset} type="button">
          <RotateCcw size={14} /> Reset
        </button>
      </div>
    </section>
  );
}
