export const queryKeys = {
  me: {
    principal: ["me", "principal"] as const,
    profile: ["me", "profile"] as const,
    readiness: ["me", "readiness"] as const,
    competencies: ["me", "competencies"] as const,
    evidence: ["me", "evidence"] as const,
    nextAction: ["me", "next-action"] as const,
  },
  questions: {
    root: ["questions"] as const,
    list: (filters: Record<string, string | number | undefined>) =>
      ["questions", "list", filters] as const,
    detail: (slug: string) => ["questions", "detail", slug] as const,
  },
  practice: {
    root: ["practice"] as const,
    sessions: ["practice", "sessions"] as const,
    session: (id: string) => ["practice", "session", id] as const,
    submissions: (id: string) => ["practice", "session", id, "submissions"] as const,
  },
  submissions: {
    root: ["submissions"] as const,
    detail: (id: string) => ["submissions", id] as const,
  },
  execution: {
    status: (executionId: string) => ["execution", executionId] as const,
  },
} as const;
