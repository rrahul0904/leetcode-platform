export type JournalArticle = {
  slug: string;
  category: "Engineering systems" | "Interview craft" | "Staff leadership" | "AI infrastructure";
  title: string;
  dek: string;
  publishedAt: string;
  readMinutes: number;
  accent: "coral" | "gold" | "violet" | "teal";
  lead: string;
  sections: readonly {
    heading: string;
    paragraphs: readonly string[];
    code?: string;
  }[];
};

export type LearningResource = {
  title: string;
  description: string;
  category: "Foundations" | "Practice systems" | "Reference" | "Career strategy";
  format: "Guide" | "Checklist" | "Workbook" | "Reference";
  minutes: number;
  href: string;
};

export const journalArticles: readonly JournalArticle[] = [
  {
    slug: "reliability-before-scale",
    category: "Engineering systems",
    title: "Reliability before scale",
    dek: "Why the strongest senior-level answers begin with invariants, ownership, and failure evidence—not a larger fleet.",
    publishedAt: "August 2, 2026",
    readMinutes: 8,
    accent: "coral",
    lead:
      "Interviewers are rarely testing whether you know that horizontal scaling exists. They are testing whether you can identify the boundary that is already failing before multiplying it.",
    sections: [
      {
        heading: "Start with the invariant",
        paragraphs: [
          "A production incident is easier to reason about when you name the property that must remain true: one request creates one durable job, one lease has one owner, and one completion produces one candidate-safe result.",
          "Once the invariant is explicit, metrics and logs become evidence instead of decoration. Memory growth, duplicate work, or a stuck lease can be tied to a specific ownership path.",
        ],
      },
      {
        heading: "Separate acceptance from execution",
        paragraphs: [
          "A reliable execution platform acknowledges a submission only after its durable state and dispatch intent are committed together. The runner lifecycle is asynchronous and may be retried without changing the candidate contract.",
        ],
        code: `BEGIN;
INSERT INTO submissions (...);
INSERT INTO execution_outbox (...);
COMMIT;`,
      },
      {
        heading: "Scale the corrected system",
        paragraphs: [
          "Capacity becomes the right next question after ownership, cleanup, idempotency, and backpressure are understood. At that point, adding workers is an intentional throughput decision rather than an expensive way to hide a leak.",
        ],
      },
    ],
  },
  {
    slug: "designing-interview-evidence",
    category: "Interview craft",
    title: "Designing interview evidence",
    dek: "A practical method for turning a solution into proof that a senior candidate can operate the system they designed.",
    publishedAt: "July 30, 2026",
    readMinutes: 7,
    accent: "gold",
    lead:
      "A technically correct answer is only the beginning. Senior interview performance improves when every decision is connected to a failure mode and a verification signal.",
    sections: [
      {
        heading: "Use a decision record",
        paragraphs: [
          "State the constraint, the decision, the alternative you rejected, and the evidence that would change your mind. This keeps the conversation concrete and gives the interviewer useful places to probe.",
        ],
      },
      {
        heading: "Choose observable proof",
        paragraphs: [
          "Prefer evidence that can be demonstrated: a denied network connection from a live sandbox, a migration cycle against an empty database, or an idempotent retry that returns the original result.",
          "Source code is supporting material. Runtime behavior is the stronger claim.",
        ],
      },
    ],
  },
  {
    slug: "sql-is-an-execution-environment",
    category: "Engineering systems",
    title: "SQL is an execution environment",
    dek: "Treating schema, fixtures, privileges, and query plans as part of the candidate contract.",
    publishedAt: "July 27, 2026",
    readMinutes: 9,
    accent: "teal",
    lead:
      "A SQL workspace is not a textarea connected to the application database. It is a controlled execution environment with its own fixtures, limits, and evidence.",
    sections: [
      {
        heading: "Every test owns its database state",
        paragraphs: [
          "Hidden tests must be able to declare DDL and seed data independently. Reusing mutable state across tests creates order dependence and makes failures impossible to interpret.",
        ],
      },
      {
        heading: "Privileges are part of correctness",
        paragraphs: [
          "The candidate role should not create databases, roles, extensions, server-side programs, or read host files. A query can be semantically correct and still violate the execution boundary.",
        ],
      },
    ],
  },
  {
    slug: "the-staff-level-tradeoff",
    category: "Staff leadership",
    title: "The staff-level tradeoff",
    dek: "How to make a recommendation when delivery pressure, security, and incomplete evidence all arrive together.",
    publishedAt: "July 24, 2026",
    readMinutes: 6,
    accent: "violet",
    lead:
      "Staff judgment is visible in what you refuse to call complete. A mergeable pull request is not the same thing as a production-ready system.",
    sections: [
      {
        heading: "Classify the remaining risk",
        paragraphs: [
          "A naming inconsistency and a network-isolation defect do not belong in the same backlog bucket. Release-blocking risk should be tied to the user or system boundary it can violate.",
        ],
      },
      {
        heading: "Freeze scope without freezing progress",
        paragraphs: [
          "Stop adding features, close the critical defects, and validate the exact head that will merge. This is faster than carrying ambiguity into staging and rediscovering it through incident response.",
        ],
      },
    ],
  },
  {
    slug: "ai-infrastructure-needs-evaluation-infrastructure",
    category: "AI infrastructure",
    title: "AI infrastructure needs evaluation infrastructure",
    dek: "Why model calls, prompts, datasets, and release decisions need one traceable evidence chain.",
    publishedAt: "July 21, 2026",
    readMinutes: 10,
    accent: "coral",
    lead:
      "An AI feature becomes operable when its behavior can be reproduced, compared, and gated. Without evaluation infrastructure, model quality is an anecdote.",
    sections: [
      {
        heading: "Version the full interaction",
        paragraphs: [
          "Model identifier, prompt version, tool configuration, retrieval inputs, and policy settings should travel with every evaluation result. The output alone is not enough to explain a change.",
        ],
      },
      {
        heading: "Keep release criteria explicit",
        paragraphs: [
          "Quality, latency, safety, and cost thresholds should be evaluated against a named dataset before a model or prompt is promoted. Human review remains a first-class signal for ambiguous failure modes.",
        ],
      },
    ],
  },
  {
    slug: "practice-with-a-recovery-loop",
    category: "Interview craft",
    title: "Practice with a recovery loop",
    dek: "A study session should end with the next weak concept already scheduled—not a vague promise to revisit it.",
    publishedAt: "July 18, 2026",
    readMinutes: 5,
    accent: "gold",
    lead:
      "Solving more questions is not automatically deliberate practice. The highest-value signal is what changed in your next attempt.",
    sections: [
      {
        heading: "Record the failure precisely",
        paragraphs: [
          "Was the gap conceptual, implementation-specific, caused by time pressure, or created by an unstated assumption? Each failure type needs a different recovery task.",
        ],
      },
      {
        heading: "Schedule the narrower follow-up",
        paragraphs: [
          "The next task should isolate the missed skill, arrive after a useful delay, and remain small enough to complete. This is how progress becomes cumulative rather than episodic.",
        ],
      },
    ],
  },
] as const;

export const learningResources: readonly LearningResource[] = [
  {
    title: "System-design opening checklist",
    description: "A two-minute sequence for constraints, scale, invariants, and the first architecture boundary.",
    category: "Practice systems",
    format: "Checklist",
    minutes: 8,
    href: "/system-design-library",
  },
  {
    title: "Python execution-contract guide",
    description: "Entrypoints, invocation modes, deterministic tests, limits, and candidate-safe results.",
    category: "Reference",
    format: "Guide",
    minutes: 18,
    href: "/problems?language=python",
  },
  {
    title: "SQL sandbox readiness reference",
    description: "Fixture isolation, role restrictions, statement limits, query plans, and failure evidence.",
    category: "Reference",
    format: "Reference",
    minutes: 20,
    href: "/problems?language=sql",
  },
  {
    title: "Staff decision-record workbook",
    description: "Capture the constraint, decision, rejected alternative, risk, and validation signal.",
    category: "Career strategy",
    format: "Workbook",
    minutes: 25,
    href: "/learning-paths",
  },
  {
    title: "Distributed-systems failure map",
    description: "A compact reference for retries, leases, ordering, backpressure, and reconciliation.",
    category: "Foundations",
    format: "Reference",
    minutes: 16,
    href: "/problems?topic=distributed-systems",
  },
  {
    title: "AI evaluation release checklist",
    description: "Dataset, prompt, model, safety, latency, cost, and human-review gates in one sequence.",
    category: "Practice systems",
    format: "Checklist",
    minutes: 12,
    href: "/learning-paths",
  },
  {
    title: "Interview recovery-loop guide",
    description: "Turn a failed attempt into a classified weakness, a narrow follow-up, and a scheduled revision.",
    category: "Career strategy",
    format: "Guide",
    minutes: 14,
    href: "/progress",
  },
  {
    title: "Data-modeling review canvas",
    description: "Entities, ownership, temporal semantics, constraints, access paths, and migration strategy.",
    category: "Foundations",
    format: "Workbook",
    minutes: 30,
    href: "/question-bank?track=data-modeling",
  },
] as const;

export function journalArticle(slug: string) {
  return journalArticles.find((article) => article.slug === slug);
}
