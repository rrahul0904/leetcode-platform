"use client";

import { ChevronLeft, ChevronRight, CircleStop, ListTree } from "lucide-react";
import { useMemo, useState } from "react";

import {
  formatTraceValue,
  normalizeExecutionTrace,
  replayExecutionTrace,
  type ExecutionTrace,
} from "@/lib/execution-trace";

import styles from "./execution-trace-panel.module.css";

type ExecutionTracePanelProps = {
  trace: ExecutionTrace;
};

export function ExecutionTracePanel({ trace }: ExecutionTracePanelProps) {
  const normalized = useMemo(() => normalizeExecutionTrace(trace), [trace]);
  const [index, setIndex] = useState(() => (normalized.events.length > 0 ? 0 : -1));
  const safeIndex = Math.min(index, normalized.events.length - 1);
  const state = useMemo(
    () => replayExecutionTrace(normalized, safeIndex),
    [normalized, safeIndex],
  );
  const bindings = Object.entries(state.bindings).sort(([left], [right]) =>
    left.localeCompare(right),
  );

  function select(nextIndex: number) {
    setIndex(Math.max(-1, Math.min(nextIndex, normalized.events.length - 1)));
  }

  return (
    <section className={styles.panel} aria-label="Execution trace replay">
      <header className={styles.header}>
        <div>
          <ListTree size={17} />
          <strong>Trace Lab</strong>
          <span>{normalized.runtime}</span>
        </div>
        <div>
          <span>
            {normalized.events.length === 0 ? 0 : safeIndex + 1}/{normalized.events.length}
          </span>
          {normalized.truncated && <span className={styles.warning}>trace truncated</span>}
        </div>
      </header>

      <div className={styles.controls}>
        <button
          type="button"
          onClick={() => select(safeIndex - 1)}
          disabled={safeIndex < 0}
          aria-label="Previous trace step"
        >
          <ChevronLeft size={15} /> Previous
        </button>
        <input
          aria-label="Trace step"
          type="range"
          min={normalized.events.length > 0 ? 0 : -1}
          max={Math.max(-1, normalized.events.length - 1)}
          value={safeIndex}
          disabled={normalized.events.length === 0}
          onChange={(event) => select(Number(event.target.value))}
        />
        <button
          type="button"
          onClick={() => select(safeIndex + 1)}
          disabled={safeIndex >= normalized.events.length - 1}
          aria-label="Next trace step"
        >
          Next <ChevronRight size={15} />
        </button>
      </div>

      <div className={styles.summary}>
        <div>
          <span>Event</span>
          <strong>{state.event?.kind ?? "not started"}</strong>
        </div>
        <div>
          <span>Source</span>
          <strong>
            {state.event?.location ? `line ${state.event.location.line}` : "—"}
          </strong>
        </div>
        <div>
          <span>Outcome</span>
          <strong>{normalized.outcome.status}</strong>
        </div>
      </div>

      {state.event?.summary && <p className={styles.eventSummary}>{state.event.summary}</p>}

      <div className={styles.inspectors}>
        <section>
          <h4>Variables</h4>
          {bindings.length === 0 ? (
            <p className={styles.empty}>No captured bindings at this step.</p>
          ) : (
            <dl>
              {bindings.map(([name, value]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{formatTraceValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>

        <section>
          <h4>Call stack</h4>
          {state.stack.length === 0 ? (
            <p className={styles.empty}>No captured frames at this step.</p>
          ) : (
            <ol className={styles.stack}>
              {state.stack
                .slice()
                .reverse()
                .map((frame) => (
                  <li key={frame.id}>
                    <strong>{frame.name}</strong>
                    <span>{frame.location ? `line ${frame.location.line}` : ""}</span>
                  </li>
                ))}
            </ol>
          )}
        </section>
      </div>

      {(state.stdout || state.stderr) && (
        <section className={styles.output}>
          <h4>Output</h4>
          {state.stdout && <pre>{state.stdout}</pre>}
          {state.stderr && <pre className={styles.stderr}>{state.stderr}</pre>}
        </section>
      )}

      {normalized.outcome.status !== "completed" && normalized.outcome.message && (
        <footer className={styles.failure}>
          <CircleStop size={15} /> {normalized.outcome.message}
        </footer>
      )}
    </section>
  );
}
