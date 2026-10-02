/**
 * Falling Words: independently specified rules; RE-326 is a repository-history collision alias.
 *
 * No browser, storage, terminal, timer, or third-party game dependency. Consumers
 * must explicitly supply a monotonic clock and a deterministic [0, 1) RNG.
 * The injected clock timestamps runs; tick(deltaMs) is the sole simulation clock.
 */

export type RunState = "menu" | "ready" | "playing" | "paused" | "won" | "lost" | "exited";
export type FinishReason = "won" | "lost" | "exited";

export interface FallingWord {
  readonly id: number;
  readonly text: string;
  readonly x: number;
  readonly y: number;
}

export interface RunResult {
  readonly runId: number;
  readonly reason: FinishReason;
  readonly score: number;
  readonly level: number;
  readonly lives: number;
  readonly matchedWords: number;
  readonly missedWords: number;
  readonly activeElapsedMs: number;
  readonly startedAtMs: number;
  readonly finishedAtMs: number;
}

export interface GameSnapshot {
  readonly state: RunState;
  readonly runId: number | null;
  readonly width: number;
  readonly height: number;
  readonly words: readonly FallingWord[];
  readonly score: number;
  readonly level: number;
  readonly lives: number;
  readonly matchedWords: number;
  readonly missedWords: number;
  readonly activeElapsedMs: number;
  readonly lastResult: RunResult | null;
  readonly results: readonly RunResult[];
}

export interface GameConfig {
  readonly width: number;
  readonly height: number;
  readonly words: readonly string[];
  readonly startingLives?: number;
  readonly pointsPerLevel?: number;
  readonly winningLevel?: number;
}

export interface GameDependencies {
  readonly now: () => number;
  readonly random: () => number;
}

const POINTS_PER_CHARACTER = 10;
const INITIAL_SPAWN_MS = 2400;
const INITIAL_MOVE_MS = 650;
const SPAWN_FLOOR_MS = 450;
const MOVE_FLOOR_MS = 120;
const MAX_TICK_MS = 60_000;

function integerInRange(value: number, name: string, min: number, max: number): number {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new RangeError(name + " must be an integer between " + min + " and " + max);
  }
  return value;
}

export class GameEngine {
  private readonly width: number;
  private readonly height: number;
  private readonly pool: readonly string[];
  private startingLives: number;
  private readonly pointsPerLevel: number;
  private readonly winningLevel: number;
  private readonly now: () => number;
  private readonly random: () => number;

  private phase: RunState = "menu";
  private activeRunId: number | null = null;
  private nextRunId = 1;
  private nextWordId = 1;
  private onBoard: FallingWord[] = [];
  private scoreValue = 0;
  private livesValue: number;
  private matchedValue = 0;
  private missedValue = 0;
  private elapsedValue = 0;
  private untilSpawn = INITIAL_SPAWN_MS;
  private untilMove = INITIAL_MOVE_MS;
  private startedAt = 0;
  private lastClock: number | null = null;
  private completed: RunResult[] = [];

  constructor(config: GameConfig, dependencies: GameDependencies) {
    this.width = integerInRange(config.width, "width", 1, 200);
    this.height = integerInRange(config.height, "height", 1, 2000);
    this.startingLives = integerInRange(config.startingLives ?? 3, "startingLives", 1, 99);
    this.pointsPerLevel = integerInRange(config.pointsPerLevel ?? 150, "pointsPerLevel", 1, 100_000);
    this.winningLevel = integerInRange(config.winningLevel ?? 27, "winningLevel", 2, 27);
    if (!Array.isArray(config.words) || config.words.length < 1 || config.words.length > 1000) {
      throw new RangeError("words must contain 1 to 1000 entries");
    }
    if (config.words.some((word) =>
      typeof word !== "string" || word.length === 0 || word.length > 64 ||
      !/^[\x20-\x7e]+$/.test(word) || word.trim() !== word
    )) {
      throw new RangeError("words must be 1-64 printable ASCII characters without edge spaces");
    }
    const eligible = config.words.filter((word) => word.length <= this.width);
    if (eligible.length === 0) {
      throw new RangeError("at least one word must fit the board width");
    }
    if (typeof dependencies.now !== "function" || typeof dependencies.random !== "function") {
      throw new TypeError("now and random must be injected");
    }
    this.pool = eligible.slice();
    this.now = dependencies.now;
    this.random = dependencies.random;
    this.livesValue = this.startingLives;
  }

  get snapshot(): GameSnapshot {
    return {
      state: this.phase,
      runId: this.activeRunId,
      width: this.width,
      height: this.height,
      words: this.onBoard.map((word) => ({ ...word })),
      score: this.scoreValue,
      level: this.level,
      lives: this.livesValue,
      matchedWords: this.matchedValue,
      missedWords: this.missedValue,
      activeElapsedMs: this.elapsedValue,
      lastResult: this.completed.length > 0 ? { ...this.completed[this.completed.length - 1]! } : null,
      results: this.completed.map((result) => ({ ...result })),
    };
  }

  private get level(): number {
    return Math.min(this.winningLevel, 1 + Math.floor(this.scoreValue / this.pointsPerLevel));
  }

  private clock(): number {
    const reading = this.now();
    if (!Number.isFinite(reading) || reading < 0) {
      throw new RangeError("injected clock must return a finite nonnegative time");
    }
    this.lastClock = Math.max(this.lastClock ?? reading, reading);
    return this.lastClock;
  }

  private draw(): number {
    const value = this.random();
    if (!Number.isFinite(value) || value < 0 || value >= 1) {
      throw new RangeError("injected RNG must return a finite number in [0, 1)");
    }
    return value;
  }

  private spawnInterval(): number {
    return Math.max(SPAWN_FLOOR_MS, Math.round(INITIAL_SPAWN_MS * 0.85 ** (this.level - 1)));
  }

  private moveInterval(): number {
    return Math.max(MOVE_FLOOR_MS, Math.round(INITIAL_MOVE_MS * 0.85 ** (this.level - 1)));
  }

  /** A menu is not a running session; opening the ready screen records nothing. */
  prepare(): boolean {
    if (this.phase !== "menu") return false;
    this.phase = "ready";
    return true;
  }

  /** Device-level difficulty may change only between runs. */
  setStartingLives(value: number): boolean {
    const lives = integerInRange(value, "startingLives", 1, 99);
    if (this.phase !== "menu" && this.phase !== "ready" && this.phase !== "won" &&
        this.phase !== "lost" && this.phase !== "exited") return false;
    this.startingLives = lives;
    this.livesValue = lives;
    return true;
  }

  start(): boolean {
    if (this.phase !== "ready") return false;
    const instant = this.clock();
    this.activeRunId = this.nextRunId++;
    this.startedAt = instant;
    this.phase = "playing";
    return true;
  }

  pause(): boolean {
    if (this.phase !== "playing") return false;
    this.phase = "paused";
    return true;
  }

  resume(): boolean {
    if (this.phase !== "paused") return false;
    this.phase = "playing";
    return true;
  }

  private finish(reason: FinishReason): void {
    if (this.phase !== "playing" && this.phase !== "paused") return;
    const finishedAt = this.clock();
    this.completed.push({
      runId: this.activeRunId!,
      reason,
      score: this.scoreValue,
      level: this.level,
      lives: this.livesValue,
      matchedWords: this.matchedValue,
      missedWords: this.missedValue,
      activeElapsedMs: this.elapsedValue,
      startedAtMs: this.startedAt,
      finishedAtMs: finishedAt,
    });
    this.phase = reason;
  }

  /** A restart abandons one active run, if any, exactly once and returns to ready. */
  restart(): void {
    this.finish("exited");
    this.activeRunId = null;
    this.onBoard = [];
    this.scoreValue = 0;
    this.livesValue = this.startingLives;
    this.matchedValue = 0;
    this.missedValue = 0;
    this.elapsedValue = 0;
    this.untilSpawn = INITIAL_SPAWN_MS;
    this.untilMove = INITIAL_MOVE_MS;
    this.nextWordId = 1;
    this.phase = "ready";
  }

  exit(): void {
    this.finish("exited");
    this.phase = "exited";
  }

  /**
   * Exact, case-sensitive full-string match. When duplicate labels exist,
   * choose the lowest visible item (largest y), then the oldest id.
   * A miss or terminal state cannot be undone by a late input.
   */
  submit(text: string): number | null {
    if (this.phase !== "playing" || typeof text !== "string" || text.length === 0) return null;
    const matches = this.onBoard.filter((word) => word.text === text)
      .sort((left, right) => right.y - left.y || left.id - right.id);
    const target = matches[0];
    if (!target) return null;
    this.onBoard = this.onBoard.filter((word) => word.id !== target.id);
    this.matchedValue++;
    // Every displayed printable character, including internal spaces and punctuation, scores.
    this.scoreValue += [...target.text].length * POINTS_PER_CHARACTER;
    if (this.level === this.winningLevel) this.finish("won");
    return target.id;
  }

  private spawn(): void {
    const text = this.pool[Math.floor(this.draw() * this.pool.length)]!;
    const available: number[] = [];
    for (let x = 0; x <= this.width - text.length; x++) {
      const intersects = this.onBoard.some((word) =>
        word.y === 0 && x < word.x + word.text.length && word.x < x + text.length
      );
      if (!intersects) available.push(x);
    }
    if (available.length === 0) return; // A crowded entry row postpones this spawn.
    const x = available[Math.floor(this.draw() * available.length)]!;
    this.onBoard.push({ id: this.nextWordId++, text, x, y: 0 });
  }

  private advance(): void {
    const remaining: FallingWord[] = [];
    let misses = 0;
    for (const word of this.onBoard) {
      if (word.y + 1 >= this.height) misses++;
      else remaining.push({ ...word, y: word.y + 1 });
    }
    this.onBoard = remaining;
    if (misses > 0) {
      this.missedValue += misses;
      this.livesValue = Math.max(0, this.livesValue - misses);
      if (this.livesValue === 0) this.finish("lost");
    }
  }

  /**
   * Advance a bounded simulation delta. Movement wins an equal-time tie with
   * spawning, so words falling off the board cannot be rescued by a new spawn.
   * Pending intervals remain scheduled when scoring changes the level; the
   * next interval uses the new level. Paused/terminal ticks never consume time.
   */
  tick(deltaMs: number): void {
    if (!Number.isFinite(deltaMs) || deltaMs < 0 || deltaMs > MAX_TICK_MS) {
      throw new RangeError("deltaMs must be finite and between 0 and 60000");
    }
    if (this.phase !== "playing" || deltaMs === 0) return;
    let remaining = deltaMs;
    while (remaining > 0 && this.phase === "playing") {
      const untilEvent = Math.min(this.untilMove, this.untilSpawn);
      if (remaining < untilEvent) {
        this.untilMove -= remaining;
        this.untilSpawn -= remaining;
        this.elapsedValue += remaining;
        break;
      }
      remaining -= untilEvent;
      this.elapsedValue += untilEvent;
      this.untilMove -= untilEvent;
      this.untilSpawn -= untilEvent;
      if (this.untilMove <= 0) {
        this.advance();
        this.untilMove = this.moveInterval();
      }
      if (this.phase === "playing" && this.untilSpawn <= 0) {
        this.spawn();
        this.untilSpawn = this.spawnInterval();
      }
    }
  }
}
