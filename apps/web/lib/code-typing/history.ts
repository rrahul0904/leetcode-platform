import { sessionMetrics, type TypingSession } from "./engine";
import { SNIPPETS, type TypingLanguage } from "./snippets";

export const HISTORY_KEY = "rigor.code-typing.guest-history.v1";
export type HistoryEntry = {
  schemaVersion: 1;
  id: string;
  snippetId: string;
  snippetVersion: number;
  language: TypingLanguage;
  status: "completed" | "timed-out";
  durationSeconds: number;
  elapsedMs: number;
  correctChars: number;
  insertedChars: number;
  cpm: number;
  grossCpm: number;
  wpm: number;
  accuracy: number;
  recordedAtMs: number;
};
export function historyEntry(session: TypingSession, id: string, recordedAtMs: number): HistoryEntry {
  if (session.status !== "completed" && session.status !== "timed-out") {
    throw new Error("Only completed or timed-out attempts can enter history.");
  }
  const score = sessionMetrics(session);
  return {
    schemaVersion: 1, id, snippetId: session.snippet.id,
    snippetVersion: session.snippet.version, language: session.snippet.language,
    status: session.status, durationSeconds: session.durationMs / 1000,
    elapsedMs: session.elapsedMs, correctChars: score.correctChars,
    insertedChars: score.insertedChars, cpm: score.cpm,
    grossCpm: score.grossCpm, wpm: score.wpm, accuracy: score.accuracy,
    recordedAtMs,
  };
}
function isHistoryEntry(value: unknown): value is HistoryEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Partial<HistoryEntry>;
  const snippet = SNIPPETS.find((item) =>
    item.id === entry.snippetId && item.version === entry.snippetVersion && item.language === entry.language);
  return entry.schemaVersion === 1 && typeof entry.id === "string" && entry.id.length > 0 &&
    Boolean(snippet) && (entry.status === "completed" || entry.status === "timed-out") &&
    ([30, 60, 120] as number[]).includes(entry.durationSeconds ?? -1) &&
    (["elapsedMs", "correctChars", "insertedChars", "cpm", "grossCpm", "wpm", "accuracy", "recordedAtMs"] as const)
      .every((key) => typeof entry[key] === "number" && Number.isFinite(entry[key]) && entry[key] >= 0) &&
    (entry.accuracy ?? 101) <= 100 && (entry.elapsedMs ?? -1) <= (entry.durationSeconds ?? 0) * 1000;
}
export function readHistory(storage: Pick<Storage, "getItem">): HistoryEntry[] {
  try {
    const payload = JSON.parse(storage.getItem(HISTORY_KEY) ?? "null") as unknown;
    if (!payload || typeof payload !== "object") return [];
    const data = payload as { schemaVersion?: number; entries?: unknown };
    if (data.schemaVersion !== 1 || !Array.isArray(data.entries)) return [];
    return data.entries.filter(isHistoryEntry).slice(0, 30);
  } catch {
    return [];
  }
}
export function appendHistory(storage: Pick<Storage, "getItem" | "setItem">, entry: HistoryEntry): HistoryEntry[] {
  const existing = readHistory(storage);
  const entries = existing.some((item) => item.id === entry.id)
    ? existing : [entry, ...existing].slice(0, 30);
  storage.setItem(HISTORY_KEY, JSON.stringify({ schemaVersion: 1, entries }));
  return entries;
}
export function clearHistory(storage: Pick<Storage, "removeItem">): void {
  storage.removeItem(HISTORY_KEY);
}
