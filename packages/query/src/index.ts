export const queryKeys = {
  me: {
    profile: ["me", "profile"] as const,
    readiness: ["me", "readiness"] as const,
    evidence: ["me", "evidence"] as const,
    nextAction: ["me", "next-action"] as const,
  },
  questions: {
    root: ["questions"] as const,
    detail: (slug: string) => ["questions", "detail", slug] as const,
  },
  practice: {
    root: ["practice"] as const,
    session: (id: string) => ["practice", "session", id] as const,
    submissions: (id: string) =>
      ["practice", "session", id, "submissions"] as const,
  },
  interviews: {
    root: ["interviews"] as const,
    detail: (id: string) => ["interviews", "detail", id] as const,
  },
  execution: {
    status: (executionId: string) => ["execution", executionId] as const,
  },
} as const;

export type QueryKeys = typeof queryKeys;
