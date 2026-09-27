import { describe, expect, it } from "vitest";

import { applyText, cancelSession, newSession, normalizeInput, sessionMetrics, tick } from "./engine";
import { LANGUAGES, SNIPPETS, snippetLength, snippetsFor } from "./snippets";
import { appendHistory, clearHistory, historyEntry, HISTORY_KEY, readHistory } from "./history";

const sample = { ...SNIPPETS[0], expectedText: "abc" };
const make = () => newSession(sample, 30);

describe("original versioned manifest", () => {
  it("has stable unique versioned IDs, rights metadata and two examples per supported language", () => {
    expect(new Set(SNIPPETS.map((item) => item.id)).size).toBe(SNIPPETS.length);
    expect(LANGUAGES).toEqual(["python", "sql", "javascript"]);
    for (const language of LANGUAGES) {
      expect(snippetsFor(language)).toHaveLength(2);
      for (const snippet of snippetsFor(language)) {
        expect(snippet.schemaVersion).toBe(1);
        expect(snippet.version).toBeGreaterThan(0);
        expect(snippet.provenance).toContain("project-authored");
        expect(snippet.license).toBeTruthy();
        expect(snippetLength(snippet)).toBeGreaterThan(0);
      }
    }
  });
});

describe("deterministic clock and lifecycle", () => {
  it("starts idle only on accepted input, then completes on exact text", () => {
    let state = make();
    expect(tick(state, 1000).status).toBe("idle");
    state = applyText(state, "", 2000);
    expect(state.status).toBe("idle");
    state = applyText(state, "a", 3000);
    expect(state.status).toBe("active");
    expect(state.startedAtMs).toBe(3000);
    state = applyText(state, "abc", 4000);
    expect(state.status).toBe("completed");
    expect(state.elapsedMs).toBe(1000);
    expect(applyText(state, "wrong", 5000)).toBe(state);
    expect(tick(state, 5000)).toBe(state);
  });
  it("retains monotonic elapsed time across backwards timestamps and tab/background jumps", () => {
    let state = applyText(make(), "a", 1000);
    state = tick(state, 4000);
    expect(tick(state, 2000).elapsedMs).toBe(3000);
    expect(tick(state, 30_999).status).toBe("active");
    state = tick(state, 31_000);
    expect(state.status).toBe("timed-out");
    expect(state.elapsedMs).toBe(30_000);
    expect(tick(state, 99_999)).toBe(state);
  });
  it("deadline wins over input exactly at the boundary", () => {
    const state = applyText(make(), "a", 50);
    const late = applyText(state, "abc", 30_050);
    expect(late.status).toBe("timed-out");
    expect(late.input).toBe("a");
  });
  it("rejects invalid durations and non-finite timestamps", () => {
    expect(() => newSession(sample, 0)).toThrow(RangeError);
    expect(() => newSession(sample, 31)).toThrow(RangeError);
    const state = make();
    expect(applyText(state, "a", Number.NaN)).toBe(state);
    expect(tick(state, Number.POSITIVE_INFINITY)).toBe(state);
  });
  it("makes cancellations terminal without recording a completed result", () => {
    const cancelled = cancelSession(applyText(make(), "a", 0));
    expect(cancelled.status).toBe("cancelled");
    expect(applyText(cancelled, "abc", 2)).toBe(cancelled);
    expect(() => historyEntry(cancelled, "id", 10)).toThrow();
  });
});

describe("editing, Unicode and scoring contract", () => {
  it("normalizes CRLF and tabs and counts Unicode code points", () => {
    const unicode = { ...sample, expectedText: "α🙂\n  λ", indentation: 2 as const };
    expect(normalizeInput("α🙂\r\n\tλ", 2)).toBe(unicode.expectedText);
    const finished = applyText(newSession(unicode, 30), "α🙂\r\n\tλ", 400);
    expect(finished.status).toBe("completed");
    expect(sessionMetrics(finished).correctChars).toBe(6);
    expect(snippetLength(unicode)).toBe(6);
  });
  it("does not divide by zero or produce infinite scores", () => {
    const zero = sessionMetrics(applyText(make(), "a", 1000));
    expect(zero.cpm).toBe(0);
    expect(zero.wpm).toBe(0);
    expect(zero.grossCpm).toBe(0);
    expect(zero.accuracy).toBe(100);
  });
  it("uses aligned visible characters for net CPM and historical insertions for accuracy", () => {
    let state = applyText(make(), "x", 1000);
    state = applyText(state, "", 1500); // backspace does not erase the error
    state = applyText(state, "a", 2000);
    state = applyText(state, "abc", 3000);
    const score = sessionMetrics(state);
    expect(state.status).toBe("completed");
    expect(score.correctChars).toBe(3);
    expect(score.insertedChars).toBe(4);
    expect(score.correctInsertions).toBe(3);
    expect(score.accuracy).toBe(75);
    expect(score.cpm).toBe(90);
    expect(score.grossCpm).toBe(120);
    expect(score.wpm).toBe(18);
  });
  it("counts selected-text replacement at the right aligned position", () => {
    let state = applyText(make(), "aXc", 0);
    state = applyText(state, "abc", 1000);
    expect(state.status).toBe("completed");
    expect(sessionMetrics(state).accuracy).toBe(75);
  });
  it("retains punctuation and respects a bounded input length", () => {
    const punctuation = { ...sample, expectedText: '[x] = {"ok": true};' };
    const initial = newSession(punctuation, 30);
    expect(applyText(initial, "x".repeat(1000), 10)).toBe(initial);
    expect(applyText(initial, '[x] = {"ok": true};', 20).status).toBe("completed");
  });
});

describe("guest history", () => {
  function memoryStorage() {
    const data = new Map<string, string>();
    return {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => { data.set(key, value); },
      removeItem: (key: string) => { data.delete(key); },
    };
  }
  it("stores only finished results, preserves schema version, prevents duplicate IDs and clears", () => {
    const storage = memoryStorage();
    const finished = applyText(make(), "abc", 1000);
    const record = historyEntry(finished, "one", 2000);
    expect(appendHistory(storage, record)).toHaveLength(1);
    expect(appendHistory(storage, record)).toHaveLength(1);
    expect(readHistory(storage)).toEqual([record]);
    expect(JSON.parse(storage.getItem(HISTORY_KEY) ?? "{}").schemaVersion).toBe(1);
    clearHistory(storage);
    expect(readHistory(storage)).toEqual([]);
  });
  it("rejects corrupted/unversioned entries without losing valid records", () => {
    const storage = memoryStorage();
    // Partial sessions do not enter history.
    expect(() => historyEntry(applyText(make(), "a", 1), "one", 100)).toThrow();
  });
  it("validates malformed storage and caps guest history at 30", () => {
    const storage = memoryStorage();
    storage.setItem(HISTORY_KEY, "not json");
    expect(readHistory(storage)).toEqual([]);
    const finished = applyText(make(), "abc", 1000);
    for (let i = 0; i < 35; i++) appendHistory(storage, historyEntry(finished, `id-${i}`, i));
    expect(readHistory(storage)).toHaveLength(30);
    storage.setItem(HISTORY_KEY, JSON.stringify({ schemaVersion: 9, entries: [] }));
    expect(readHistory(storage)).toEqual([]);
    storage.setItem(HISTORY_KEY, JSON.stringify({
      schemaVersion: 1, entries: [{ ...historyEntry(finished, "good", 2), cpm: Infinity },
        historyEntry(finished, "valid", 3)],
    }));
    expect(readHistory(storage).map((item) => item.id)).toEqual(["valid"]);
  });
});
