export type TracePrimitive = string | number | boolean | null;

export type TraceValue =
  | { kind: "primitive"; value: TracePrimitive }
  | { kind: "undefined" }
  | { kind: "reference"; ref: string; preview: string; size?: number };

export type TraceSourceLocation = {
  line: number;
  column?: number;
  endLine?: number;
  endColumn?: number;
};

export type TraceBinding = {
  name: string;
  value: TraceValue;
};

export type TraceFrame = {
  id: string;
  name: string;
  location?: TraceSourceLocation;
};

export type ExecutionTraceEventKind =
  | "line"
  | "call"
  | "return"
  | "assign"
  | "write"
  | "output"
  | "exception";

export type ExecutionTraceEvent = {
  seq: number;
  kind: ExecutionTraceEventKind;
  location?: TraceSourceLocation;
  frameId?: string;
  summary?: string;
  bindings?: TraceBinding[];
  stack?: TraceFrame[];
  stdout?: string;
  stderr?: string;
};

export type ExecutionTraceLimits = {
  maxEvents: number;
  maxFrames: number;
  maxBindingsPerEvent: number;
  maxTextLength: number;
};

export type ExecutionTraceOutcome = {
  status: "completed" | "failed" | "timeout" | "cancelled";
  message?: string;
};

export type ExecutionTrace = {
  version: 1;
  runtime: string;
  events: ExecutionTraceEvent[];
  limits: ExecutionTraceLimits;
  outcome: ExecutionTraceOutcome;
  truncated: boolean;
};

export type ExecutionTraceState = {
  index: number;
  event: ExecutionTraceEvent | null;
  bindings: Record<string, TraceValue>;
  stack: TraceFrame[];
  stdout: string;
  stderr: string;
};

export const DEFAULT_EXECUTION_TRACE_LIMITS: ExecutionTraceLimits = {
  maxEvents: 5_000,
  maxFrames: 128,
  maxBindingsPerEvent: 256,
  maxTextLength: 64_000,
};

function clampText(value: string, maxLength: number) {
  return value.length <= maxLength ? value : value.slice(0, maxLength);
}

function clampBindings(bindings: TraceBinding[], maxBindings: number) {
  return bindings.slice(0, maxBindings);
}

function clampStack(stack: TraceFrame[], maxFrames: number) {
  return stack.slice(-maxFrames);
}

/**
 * Normalizes provider output at the UI trust boundary. The execution provider is
 * responsible for enforcing stronger byte/time/depth budgets while it runs; this
 * function prevents an oversized or malformed replay artifact from expanding in
 * the browser.
 */
export function normalizeExecutionTrace(trace: ExecutionTrace): ExecutionTrace {
  const limits = {
    maxEvents: Math.max(1, trace.limits.maxEvents),
    maxFrames: Math.max(1, trace.limits.maxFrames),
    maxBindingsPerEvent: Math.max(1, trace.limits.maxBindingsPerEvent),
    maxTextLength: Math.max(1, trace.limits.maxTextLength),
  };

  const sourceEvents = trace.events.slice(0, limits.maxEvents);
  let previousSeq = -1;
  const events: ExecutionTraceEvent[] = sourceEvents.map((event) => {
    if (!Number.isSafeInteger(event.seq) || event.seq <= previousSeq) {
      throw new Error("Execution trace sequence numbers must be strictly increasing");
    }
    previousSeq = event.seq;

    const normalizedEvent: ExecutionTraceEvent = {
      seq: event.seq,
      kind: event.kind,
    };
    if (event.location !== undefined) normalizedEvent.location = event.location;
    if (event.frameId !== undefined) normalizedEvent.frameId = event.frameId;
    if (event.bindings !== undefined) {
      normalizedEvent.bindings = clampBindings(event.bindings, limits.maxBindingsPerEvent);
    }
    if (event.stack !== undefined) {
      normalizedEvent.stack = clampStack(event.stack, limits.maxFrames);
    }
    if (event.stdout !== undefined) {
      normalizedEvent.stdout = clampText(event.stdout, limits.maxTextLength);
    }
    if (event.stderr !== undefined) {
      normalizedEvent.stderr = clampText(event.stderr, limits.maxTextLength);
    }
    if (event.summary !== undefined) {
      normalizedEvent.summary = clampText(event.summary, limits.maxTextLength);
    }
    return normalizedEvent;
  });

  return {
    ...trace,
    limits,
    events,
    truncated: trace.truncated || trace.events.length > events.length,
  };
}

export function replayExecutionTrace(trace: ExecutionTrace, index: number): ExecutionTraceState {
  const normalized = normalizeExecutionTrace(trace);
  const lastIndex = normalized.events.length - 1;
  const clampedIndex = Math.max(-1, Math.min(index, lastIndex));
  const bindings: Record<string, TraceValue> = {};
  let stack: TraceFrame[] = [];
  let stdout = "";
  let stderr = "";

  for (let cursor = 0; cursor <= clampedIndex; cursor += 1) {
    const event = normalized.events[cursor];
    if (!event) break;
    for (const binding of event.bindings ?? []) {
      bindings[binding.name] = binding.value;
    }
    if (event.stack !== undefined) stack = event.stack;
    if (event.stdout !== undefined) {
      stdout = clampText(`${stdout}${event.stdout}`, normalized.limits.maxTextLength);
    }
    if (event.stderr !== undefined) {
      stderr = clampText(`${stderr}${event.stderr}`, normalized.limits.maxTextLength);
    }
  }

  return {
    index: clampedIndex,
    event: clampedIndex >= 0 ? (normalized.events[clampedIndex] ?? null) : null,
    bindings,
    stack,
    stdout,
    stderr,
  };
}

export function formatTraceValue(value: TraceValue): string {
  if (value.kind === "undefined") return "undefined";
  if (value.kind === "reference") return value.preview;
  if (typeof value.value === "string") return JSON.stringify(value.value);
  return String(value.value);
}
