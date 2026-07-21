export const tracks = [
  ["", "All tracks"],
  ["python-engineering", "Python engineering"],
  ["sql-analytics", "SQL & analytics"],
  ["data-modeling", "Data modeling"],
  ["data-architecture", "Data architecture"],
  ["distributed-systems", "Distributed systems"],
  ["system-design", "System design"],
  ["ml-system-design", "ML system design"],
  ["generative-ai-architecture", "GenAI architecture"],
  ["ai-infrastructure", "AI infrastructure"],
  ["ai-safety-agents-evaluation", "AI safety & evaluation"],
  ["staff-principal-leadership", "Staff & principal"],
  ["behavioral-execution", "Behavioral execution"],
] as const;

export const difficulties = ["", "foundational", "intermediate", "advanced", "staff", "principal"] as const;

export function titleCaseSlug(value: string) {
  const known = tracks.find(([slug]) => slug === value)?.[1];
  if (known) return known;
  return value.replaceAll("-", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export const learningPaths = [
  {
    id: "backend-systems",
    title: "Senior backend systems",
    role: "Senior → Staff",
    duration: "8 weeks",
    hours: "6–8 hrs/week",
    accent: "teal",
    tracks: ["python-engineering", "sql-analytics", "distributed-systems", "system-design"],
    outcomes: ["Implementation fluency", "Failure-mode reasoning", "Capacity and API trade-offs"],
  },
  {
    id: "ai-platform",
    title: "Applied AI platform",
    role: "Senior → Principal",
    duration: "10 weeks",
    hours: "7–9 hrs/week",
    accent: "blue",
    tracks: ["ml-system-design", "generative-ai-architecture", "ai-infrastructure", "ai-safety-agents-evaluation"],
    outcomes: ["Evaluation architecture", "Serving and cost controls", "Safety and human oversight"],
  },
  {
    id: "data-architecture",
    title: "Data architecture leadership",
    role: "Staff → Principal",
    duration: "8 weeks",
    hours: "5–7 hrs/week",
    accent: "orange",
    tracks: ["sql-analytics", "data-modeling", "data-architecture", "staff-principal-leadership"],
    outcomes: ["Modeling under change", "Governance and lineage", "Strategy and migration leadership"],
  },
] as const;

export const mockFocuses = [
  { id: "coding", label: "Python coding", track: "python-engineering", phases: ["Clarify", "Implement", "Test", "Production follow-up"] },
  { id: "sql", label: "SQL reasoning", track: "sql-analytics", phases: ["Inspect schema", "Write query", "Validate edge cases", "Optimize"] },
  { id: "systems", label: "System design", track: "system-design", phases: ["Requirements", "Capacity", "Architecture", "Deep dive", "Operations"] },
  { id: "ai", label: "AI architecture", track: "generative-ai-architecture", phases: ["Use case", "Evaluation", "Architecture", "Safety", "Cost"] },
  { id: "leadership", label: "Staff leadership", track: "staff-principal-leadership", phases: ["Context", "Decisions", "Influence", "Outcomes", "Reflection"] },
] as const;

export const designTemplates = [
  {
    id: "system-design",
    title: "System design",
    description: "Capture requirements, capacity, boundaries, data flow, and failure handling.",
    nodes: ["Client", "API gateway", "Application service", "Primary database"],
  },
  {
    id: "data-platform",
    title: "Data architecture",
    description: "Map producers, contracts, ingestion, transformation, serving, and governance.",
    nodes: ["Producers", "Event bus", "Processing", "Warehouse"],
  },
  {
    id: "ai-system",
    title: "AI system",
    description: "Model retrieval, inference, policy, evaluation, telemetry, and human review.",
    nodes: ["Product", "AI gateway", "Model provider", "Evaluation store"],
  },
  {
    id: "incident-review",
    title: "Incident review",
    description: "Build a timeline with detection, containment, recovery, and follow-up ownership.",
    nodes: ["Signal", "Detection", "Mitigation", "Recovery"],
  },
] as const;

export const qualityGates = [
  ["Schema completeness", "pass", "Stable identifiers and required sidecars validate."],
  ["Reference integrity", "attention", "PY-0001 has unresolved related-question references."],
  ["Executable tests", "pass", "Public, hidden, and reference tests pass for the draft package."],
  ["Rubric integrity", "pass", "Criteria and weights validate deterministically."],
  ["Originality metadata", "pass", "Independent authorship statement and content hash are recorded."],
  ["Similarity analysis", "waiting", "Full-bank semantic comparison is not running yet."],
  ["Difficulty calibration", "waiting", "Requires reviewer evidence and outcome data."],
  ["Technical approval", "waiting", "An independent technical reviewer is not assigned."],
  ["Editorial approval", "waiting", "A different editorial reviewer is not assigned."],
  ["Immutable source revision", "waiting", "Publication commit has not been created."],
  ["Catalog synchronization", "waiting", "No version has reached the approved state."],
  ["Post-publication monitoring", "waiting", "Begins after candidate traffic exists."],
] as const;

export const reviewPackage = {
  id: "PY-0001",
  slug: "py-0001-bounded-cache",
  title: "Build a Bounded TTL-Aware LRU Cache",
  version: "0.1.0",
  state: "awaiting technical review",
  checks: "4 passed · 1 needs attention",
  owner: "rigor-founding-editor",
};
