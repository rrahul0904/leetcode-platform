import { DURATIONS, type TypingSnippet } from "./snippets";

export type SessionStatus = "idle" | "active" | "completed" | "timed-out" | "cancelled";
export type TypingSession = {
  status: SessionStatus;
  snippet: TypingSnippet;
  durationMs: number;
  input: string;
  startedAtMs: number | null;
  elapsedMs: number;
  insertedChars: number;
  correctInsertions: number;
};
export type TypingMetrics = {
  correctChars: number;
  insertedChars: number;
  correctInsertions: number;
  elapsedSeconds: number;
  cpm: number;
  grossCpm: number;
  wpm: number;
  accuracy: number;
};
export function normalizeInput(value: string, spaces: 2 | 4): string {
  return value.replace(/\r\n?/g, "\n").replace(/\t/g, " ".repeat(spaces));
}
export function newSession(snippet: TypingSnippet, durationSeconds: number): TypingSession {
  if (!DURATIONS.some((duration) => duration === durationSeconds)) {
    throw new RangeError("Duration must be 30, 60 or 120 seconds.");
  }
  return {
    status: "idle", snippet, durationMs: durationSeconds * 1000, input: "",
    startedAtMs: null, elapsedMs: 0, insertedChars: 0, correctInsertions: 0,
  };
}
export function tick(session: TypingSession, atMs: number): TypingSession {
  if (session.status !== "active" || !Number.isFinite(atMs) || session.startedAtMs === null) return session;
  const elapsedMs = Math.min(
    session.durationMs, Math.max(session.elapsedMs, 0, atMs - session.startedAtMs),
  );
  if (elapsedMs === session.elapsedMs && elapsedMs < session.durationMs) return session;
  return { ...session, elapsedMs, status: elapsedMs >= session.durationMs ? "timed-out" : "active" };
}
/** Browser textarea value after an edit. Inserted code points affect historical accuracy;
 * deletion never erases a past mistake. Paste/drop is blocked by the UI, not anti-cheat.
 */
export function applyText(session: TypingSession, rawText: string, atMs: number): TypingSession {
  if ((session.status !== "idle" && session.status !== "active") || !Number.isFinite(atMs)) return session;
  const current = tick(session, atMs);
  if (current.status === "timed-out") return current; // deadline beats late input
  const next = normalizeInput(rawText, session.snippet.indentation);
  const target = Array.from(session.snippet.expectedText);
  const before = Array.from(current.input);
  const after = Array.from(next);
  if (next === current.input || next.includes("\0") || after.length > target.length + 32) return current;
  let prefix = 0;
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix++;
  let suffix = 0;
  while (
    suffix < before.length - prefix && suffix < after.length - prefix &&
    before[before.length - 1 - suffix] === after[after.length - 1 - suffix]
  ) suffix++;
  const inserted = after.slice(prefix, after.length - suffix);
  const correct = inserted.reduce(
    (count, character, index) => count + Number(character === target[prefix + index]), 0,
  );
  const startedAtMs = current.startedAtMs ?? (next ? atMs : null);
  const status = next === session.snippet.expectedText
    ? "completed" : startedAtMs === null ? "idle" : "active";
  return {
    ...current, status, input: next, startedAtMs,
    insertedChars: current.insertedChars + inserted.length,
    correctInsertions: current.correctInsertions + correct,
  };
}
export function cancelSession(session: TypingSession): TypingSession {
  return session.status === "idle" || session.status === "active"
    ? { ...session, status: "cancelled" } : session;
}
export function sessionMetrics(session: TypingSession): TypingMetrics {
  const target = Array.from(session.snippet.expectedText);
  const actual = Array.from(session.input);
  const correctChars = actual.reduce(
    (count, character, index) => count + Number(character === target[index]), 0,
  );
  const elapsedSeconds = session.elapsedMs / 1000;
  const cpm = elapsedSeconds > 0 ? (correctChars * 60) / elapsedSeconds : 0;
  const grossCpm = elapsedSeconds > 0 ? (session.insertedChars * 60) / elapsedSeconds : 0;
  return {
    correctChars, insertedChars: session.insertedChars,
    correctInsertions: session.correctInsertions,
    elapsedSeconds, cpm, grossCpm, wpm: cpm / 5,
    accuracy: session.insertedChars > 0
      ? (session.correctInsertions / session.insertedChars) * 100 : 100,
  };
}
