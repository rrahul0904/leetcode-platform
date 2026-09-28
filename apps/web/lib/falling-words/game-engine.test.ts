import { describe, expect, it } from "vitest";

import { GameEngine, type GameConfig } from "./game-engine";

function harness(config: Partial<GameConfig> = {}, random: () => number = () => 0) {
  let time = 1_000;
  const game = new GameEngine(
    { width: 8, height: 6, words: ["cat"], ...config },
    { now: () => time, random },
  );
  return { game, setTime: (next: number) => { time = next; } };
}

function begin(game: GameEngine) {
  expect(game.prepare()).toBe(true);
  expect(game.start()).toBe(true);
}

describe("RE-326 headless falling-word GameEngine", () => {
  it("keeps finite lifecycle transitions explicit and nonduplicating", () => {
    const { game } = harness();
    expect(game.snapshot.state).toBe("menu");
    expect(game.start()).toBe(false);
    expect(game.pause()).toBe(false);
    expect(game.prepare()).toBe(true);
    expect(game.prepare()).toBe(false);
    expect(game.start()).toBe(true);
    expect(game.start()).toBe(false);
    expect(game.pause()).toBe(true);
    expect(game.pause()).toBe(false);
    expect(game.resume()).toBe(true);
    expect(game.resume()).toBe(false);
    game.exit();
    game.exit();
    expect(game.snapshot.state).toBe("exited");
    expect(game.snapshot.results).toHaveLength(1);
    expect(game.snapshot.lastResult?.reason).toBe("exited");
  });

  it("requires controlled inputs, validates board and dictionary bounds, and filters overlong entries", () => {
    for (const width of [0, -1, 1.5, Number.NaN, 201]) {
      expect(() => harness({ width })).toThrow(RangeError);
    }
    for (const height of [0, -3, 2.5, 2001]) {
      expect(() => harness({ height })).toThrow(RangeError);
    }
    for (const word of ["", " leading", "trailing ", "has\nnewline", "é", "x".repeat(65)]) {
      expect(() => harness({ words: [word] })).toThrow(RangeError);
    }
    expect(() => harness({ words: ["elephant"], width: 3 })).toThrow(RangeError);
    expect(() => harness({ startingLives: 0 })).toThrow(RangeError);
    expect(() => harness({ winningLevel: 28 })).toThrow(RangeError);
    const { game } = harness({ width: 3, words: ["elephant", "cat"] });
    begin(game);
    game.tick(2400);
    expect(game.snapshot.words.map((word) => word.text)).toEqual(["cat"]);
  });

  it("validates deltas even when inactive and rejects broken RNG and clock inputs", () => {
    const { game } = harness();
    for (const delta of [-1, Infinity, NaN, 60_001]) {
      expect(() => game.tick(delta)).toThrow(RangeError);
    }
    const badRng = harness({}, () => 1).game;
    begin(badRng);
    expect(() => badRng.tick(2400)).toThrow(RangeError);
    const invalidClock = new GameEngine(
      { width: 5, height: 5, words: ["a"] },
      { now: () => Number.NaN, random: () => 0 },
    );
    invalidClock.prepare();
    expect(() => invalidClock.start()).toThrow(RangeError);
  });

  it("spawns within bounds and moves one row per scheduled movement before a single collision", () => {
    const { game, setTime } = harness({ width: 3, height: 2, words: ["cat"], startingLives: 1 });
    begin(game);
    game.tick(2399);
    expect(game.snapshot.words).toHaveLength(0);
    game.tick(1);
    expect(game.snapshot.words).toEqual([{ id: 1, text: "cat", x: 0, y: 0 }]);
    game.tick(200);
    expect(game.snapshot.words[0]?.y).toBe(1);
    setTime(4_500);
    game.tick(650);
    expect(game.snapshot.words).toHaveLength(0);
    expect(game.snapshot.lives).toBe(0);
    expect(game.snapshot.missedWords).toBe(1);
    expect(game.snapshot.state).toBe("lost");
    expect(game.snapshot.lastResult?.activeElapsedMs).toBe(3250);
    expect(game.snapshot.lastResult?.finishedAtMs).toBe(4500);
    game.tick(60_000);
    expect(game.snapshot.results).toHaveLength(1);
    expect(game.submit("cat")).toBeNull();
  });

  it("produces identical results for one large or many partitioned ticks", () => {
    const first = harness({ width: 6, height: 10, words: ["a", "bb"] });
    const second = harness({ width: 6, height: 10, words: ["a", "bb"] });
    begin(first.game);
    begin(second.game);
    first.game.tick(4800);
    second.game.tick(1600);
    second.game.tick(1600);
    second.game.tick(1600);
    expect(second.game.snapshot).toEqual(first.game.snapshot);
  });

  it("matches only an exact case-sensitive target and counts internal spaces and punctuation", () => {
    const { game } = harness({ width: 9, words: ["Red fox!"] });
    begin(game);
    game.tick(2400);
    expect(game.submit("red fox!")).toBeNull();
    expect(game.submit("Red  fox!")).toBeNull();
    expect(game.submit("Red fox! ")).toBeNull();
    expect(game.submit("Red fox!")).toBe(1);
    expect(game.snapshot.score).toBe(80);
    expect(game.snapshot.matchedWords).toBe(1);
    expect(game.snapshot.words).toHaveLength(0);
    expect(game.submit("Red fox!")).toBeNull();
  });

  it("selects the lowest duplicate target, never all identical labels", () => {
    const { game } = harness({ height: 20, words: ["a"] });
    begin(game);
    game.tick(4800);
    expect(game.snapshot.words).toHaveLength(2);
    expect(game.snapshot.words[0]!.y).toBeGreaterThan(game.snapshot.words[1]!.y);
    expect(game.submit("a")).toBe(1);
    expect(game.snapshot.words.map((word) => word.id)).toEqual([2]);
    expect(game.snapshot.score).toBe(10);
  });

  it("progresses by configured score thresholds and wins exactly once", () => {
    const { game } = harness({ words: ["a"], pointsPerLevel: 10, winningLevel: 3 });
    begin(game);
    game.tick(2400);
    expect(game.submit("a")).toBe(1);
    expect(game.snapshot.level).toBe(2);
    game.tick(2400);
    expect(game.submit("a")).toBe(2);
    expect(game.snapshot.state).toBe("won");
    expect(game.snapshot.level).toBe(3);
    expect(game.snapshot.score).toBe(20);
    expect(game.snapshot.lastResult?.reason).toBe("won");
    game.submit("a");
    game.tick(60_000);
    game.exit();
    expect(game.snapshot.results).toHaveLength(1);
    expect(game.snapshot.results[0]?.reason).toBe("won");
  });

  it("caps the score-derived progression at level 27 and terminates there", () => {
    const { game } = harness({ words: ["a"], pointsPerLevel: 1, winningLevel: 27, height: 50 });
    begin(game);
    game.tick(2400);
    game.submit("a");
    expect(game.snapshot.level).toBe(11);
    game.tick(2400);
    game.submit("a");
    expect(game.snapshot.level).toBe(21);
    game.tick(472); // The pending spawn uses the rounded interval scheduled at level 11.
    expect(game.snapshot.words).toHaveLength(2);
    expect(game.submit("a")).toBe(2); // Lowest duplicate wins even as a new word spawns.
    expect(game.snapshot.level).toBe(27);
    expect(game.snapshot.state).toBe("won");
    expect(game.snapshot.results).toHaveLength(1);
  });

  it("does not consume simulated time while paused or permit paused input", () => {
    const { game } = harness();
    begin(game);
    game.tick(2390);
    game.pause();
    const frozen = game.snapshot;
    game.tick(60_000);
    expect(game.submit("cat")).toBeNull();
    expect(game.snapshot.activeElapsedMs).toBe(frozen.activeElapsedMs);
    expect(game.snapshot.words).toEqual(frozen.words);
    game.resume();
    game.tick(10);
    expect(game.snapshot.words).toHaveLength(1);
    expect(game.snapshot.activeElapsedMs).toBe(2400);
  });

  it("records an abandoned restart once, resets run state, and keeps run IDs distinct", () => {
    const { game } = harness();
    begin(game);
    game.tick(2400);
    game.submit("cat");
    game.pause();
    game.restart();
    expect(game.snapshot.state).toBe("ready");
    expect(game.snapshot.score).toBe(0);
    expect(game.snapshot.words).toHaveLength(0);
    expect(game.snapshot.lastResult?.reason).toBe("exited");
    expect(game.snapshot.results).toHaveLength(1);
    expect(game.start()).toBe(true);
    expect(game.snapshot.runId).toBe(2);
    game.exit();
    expect(game.snapshot.results.map((result) => result.runId)).toEqual([1, 2]);
    game.restart();
    game.restart();
    expect(game.snapshot.results).toHaveLength(2);
  });

  it("uses injected clock for timestamps and clamps clock rollback, with tick-only active duration", () => {
    const { game, setTime } = harness({ words: ["a"], winningLevel: 2, pointsPerLevel: 10 });
    begin(game);
    game.tick(2400);
    setTime(500); // An unexpectedly regressing clock cannot produce negative wall time.
    game.submit("a");
    expect(game.snapshot.lastResult).toMatchObject({
      startedAtMs: 1000,
      finishedAtMs: 1000,
      activeElapsedMs: 2400,
    });
  });

  it("exposes defensive board snapshots that callers cannot use to alter simulation", () => {
    const { game } = harness();
    begin(game);
    game.tick(2400);
    const external = game.snapshot.words as Array<{ id: number; text: string; x: number; y: number }>;
    external[0]!.x = 999;
    external.pop();
    expect(game.snapshot.words).toEqual([{ id: 1, text: "cat", x: 0, y: 0 }]);
  });
});
