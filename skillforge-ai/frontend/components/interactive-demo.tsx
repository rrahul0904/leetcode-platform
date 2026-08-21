"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  Code2,
  Database,
  Moon,
  Search,
  Sparkles,
  Sun,
  Target,
} from "lucide-react";
import { RotatingGlobe } from "@/components/rotating-globe";

type Subject = {
  id: string;
  label: string;
  count: number;
  description: string;
};

type DemoQuestion = {
  id: string;
  subject: string;
  difficulty: "Easy" | "Medium" | "Hard";
  title: string;
  prompt: string;
  approach: string;
  signal: string;
};

const subjects: Subject[] = [
  { id: "python", label: "Python Coding", count: 100000, description: "Algorithms, data processing, deterministic utilities and complexity." },
  { id: "sql", label: "SQL", count: 150000, description: "Analytics, joins, windows, aggregation, correctness and performance." },
  { id: "pyspark", label: "PySpark / Spark", count: 80000, description: "Distributed transforms, skew, partitioning, streaming and Delta patterns." },
  { id: "de", label: "Data Engineering", count: 150000, description: "CDC, orchestration, quality, recovery, observability and warehouse design." },
  { id: "snowflake", label: "Snowflake", count: 80000, description: "Warehouses, Snowpipe, Streams, Tasks, governance, cost and performance." },
  { id: "databricks", label: "Databricks", count: 60000, description: "Delta Lake, Auto Loader, Unity Catalog, Photon and lakehouse operations." },
  { id: "bigquery", label: "BigQuery / GCP Data", count: 40000, description: "Partitioning, clustering, slots, Dataflow, Pub/Sub and cost controls." },
  { id: "airflow", label: "Airflow / Orchestration", count: 40000, description: "DAG design, retries, sensors, backfills, pools and idempotency." },
  { id: "aws", label: "AWS Cloud", count: 50000, description: "S3, Glue, Kinesis, Redshift, IAM, recovery and security architecture." },
  { id: "azure", label: "Azure Cloud", count: 50000, description: "ADLS, Data Factory, Event Hubs, Synapse, identity and recovery." },
  { id: "gcp", label: "GCP Cloud", count: 40000, description: "Cloud Storage, Pub/Sub, Dataflow, BigQuery, IAM and regional design." },
  { id: "system", label: "System Design", count: 50000, description: "Scalable services, queues, storage, observability and multi-region tradeoffs." },
  { id: "ai", label: "AI / LLM / Agentic AI", count: 50000, description: "RAG, agents, tools, guardrails, evaluation, routing, privacy and cost." },
  { id: "modeling", label: "Data Architecture / Modeling", count: 30000, description: "Dimensional models, data mesh, contracts, semantic layers and domain design." },
  { id: "governance", label: "Governance / Security / Lineage", count: 30000, description: "Glossary, ontology, lineage, classification, RBAC/ABAC and audit." },
];

const questions: DemoQuestion[] = [
  {
    id: "PY-000001",
    subject: "Python Coding",
    difficulty: "Medium",
    title: "Filtered aggregate under scale constraints",
    prompt: "Return the sum of values divisible by k. Treat it as a production data-processing utility: handle boundary cases, preserve deterministic output, and explain the complexity.",
    approach: "Use a single pass with conditional accumulation. Avoid building an auxiliary list unless it materially improves readability and remains within the stated space target.",
    signal: "1M-v1 · parameterized coding family",
  },
  {
    id: "SQL-000001",
    subject: "SQL",
    difficulty: "Hard",
    title: "Latest valid record per business key",
    prompt: "Design a deterministic warehouse query that keeps the latest valid event per business key while duplicate keys, NULLs and ties are possible. Explain how you would validate plan behavior at scale.",
    approach: "Rank inside each business key using an explicit ordering that includes a stable tie breaker; then filter to row 1. Inspect scan pruning, partition width, sort cost and spill risk.",
    signal: "1M-v1 · SQL analytics family",
  },
  {
    id: "PS-000001",
    subject: "PySpark / Spark",
    difficulty: "Hard",
    title: "Skew-safe large-to-small join",
    prompt: "A Spark pipeline has a severely skewed join key. Build a PySpark-oriented remediation that remains restart-safe and explain when salting, broadcast joins or repartitioning should be used.",
    approach: "Start with the data shape. Broadcast only when the smaller side safely fits executor memory; salt only the hot keys when skew persists; validate shuffle size, stage duration and partition distribution in Spark UI.",
    signal: "1M-v1 · distributed processing family",
  },
  {
    id: "SF-000001",
    subject: "Snowflake",
    difficulty: "Hard",
    title: "Separate BI and ELT without duplicating data",
    prompt: "Design or troubleshoot a Snowflake workload where interactive BI and heavy ELT contend for compute. Preserve shared governed data while reducing queue time and uncontrolled credit spend.",
    approach: "Separate workloads across independently sized virtual warehouses, use auto-suspend and resource monitors, then validate queue time, credit consumption and concurrency before and after the change.",
    signal: "1M-v1 · Snowflake scenario family",
  },
  {
    id: "SD-000001",
    subject: "System Design",
    difficulty: "Hard",
    title: "Multi-region event ingestion platform",
    prompt: "Design an event ingestion platform that tolerates retries, partial failures and regional growth while exposing latency, freshness, quality, cost and reconciliation signals.",
    approach: "Define durable boundaries first: API gateway, stateless ingestion, durable queue, primary data store/object storage, idempotency keys, observability, backfill paths and explicit failover semantics.",
    signal: "1M-v1 · system-design family",
  },
  {
    id: "AI-000001",
    subject: "AI / LLM / Agentic AI",
    difficulty: "Hard",
    title: "Enterprise RAG with permission-aware evidence",
    prompt: "Design a RAG system that reduces unsupported answers while preserving enterprise permissions, cost controls, evaluation evidence and safe tool use.",
    approach: "Filter retrieval by identity and policy before generation, require grounded answers with citation support, evaluate retrieval and answer quality separately, and isolate tool execution behind explicit schemas and least-privilege credentials.",
    signal: "1M-v1 · AI architecture family",
  },
];

const journal = [
  ["FIELD NOTE 01", "How to explain a data platform tradeoff in 90 seconds", "A practical interview framework: requirement, failure domain, design choice, downside, validation."],
  ["FIELD NOTE 02", "Snowflake cost questions are really workload questions", "Use queue time, concurrency, warehouse size, auto-suspend and normalized credit evidence instead of generic tuning advice."],
  ["FIELD NOTE 03", "System design answers need recovery paths", "The happy path is not enough. Strong answers make retries, backfills, idempotency and rollback explicit."],
  ["FIELD NOTE 04", "What interviewers listen for in PySpark", "Data shape, shuffle boundaries, skew, file size, state growth and operational proof matter more than memorized APIs."],
  ["FIELD NOTE 05", "RAG interviews: separate retrieval quality from answer quality", "A clean architecture distinguishes indexing, retrieval, grounding, evaluation, permissions and tool-risk controls."],
  ["FIELD NOTE 06", "SQL correctness before cleverness", "Make tie breakers, NULL handling, join cardinality and aggregation order explicit before discussing micro-optimizations."],
] as const;

const faqs = [
  ["Is the demo using the million-row bank directly?", "The demo uses the uploaded 1M-v1 manifest and generator families for subject coverage and representative interactions. The full Parquet corpus remains a governed import source rather than being bundled into the browser."],
  ["Are all one million rows independently authored concepts?", "No. The source manifest explicitly states that exact question text and fingerprints are unique, while concept families are parameterized across workloads, industries, constraints, scale, latency, retention and other dimensions."],
  ["What is actually interactive here?", "The globe rotates and supports drag/touch, subject coverage can be explored, questions can be searched and filtered, approaches can be revealed, the architecture answer box produces a deterministic rubric, the theme can switch, and the FAQ expands inline."],
  ["Does the demo fake AI or code execution?", "No. This public preview does not claim a model call or isolated runner when one is not configured. The rubric in this demo is deterministic and is labeled as such. The authenticated product workspace contains the real API integration work."],
  ["Can the 100K and 1M sources both be kept?", "Yes. The 100K bank is useful as a smaller validated operational slice, while the 1M bank is the broader expansion set. Both can be registered with separate provenance, checksums and import jobs."],
] as const;

function percent(count: number) {
  return `${Math.round((count / 1_000_000) * 100)}%`;
}

function rubric(text: string) {
  const normalized = text.toLowerCase();
  const checks = [
    ["architecture", /warehouse|queue|stream|storage|compute|service|pipeline|layer|catalog/],
    ["failure handling", /retry|idempot|failure|rollback|backfill|recovery|failover/],
    ["tradeoffs", /tradeoff|cost|latency|throughput|complexity|downside|credit/],
    ["validation", /monitor|metric|validate|evidence|baseline|slo|observ|query history|spark ui/],
    ["governance", /security|govern|lineage|rbac|abac|mask|permission|audit/],
  ] as const;
  const passed = checks.filter(([, rule]) => rule.test(normalized));
  const score = Math.min(100, 35 + passed.length * 12 + Math.min(5, Math.floor(text.trim().length / 160)));
  const missing = checks.filter(([name, rule]) => !rule.test(normalized)).map(([name]) => name);
  return { score, passed: passed.map(([name]) => name), missing };
}

export function InteractiveDemo() {
  const [dark, setDark] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState(subjects[0]);
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState<"All" | DemoQuestion["difficulty"]>("All");
  const [selectedQuestion, setSelectedQuestion] = useState<DemoQuestion>(questions[0]);
  const [showApproach, setShowApproach] = useState(false);
  const [answer, setAnswer] = useState("");
  const [review, setReview] = useState<ReturnType<typeof rubric> | null>(null);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return questions.filter((question) => {
      const matchesDifficulty = difficulty === "All" || question.difficulty === difficulty;
      const haystack = `${question.id} ${question.subject} ${question.title} ${question.prompt}`.toLowerCase();
      return matchesDifficulty && (!term || haystack.includes(term));
    });
  }, [difficulty, query]);

  function reviewAnswer() {
    if (!answer.trim()) {
      setReview({ score: 0, passed: [], missing: ["architecture", "failure handling", "tradeoffs", "validation", "governance"] });
      return;
    }
    setReview(rubric(answer));
  }

  return <main className={dark ? "sf-demo sf-demo-dark" : "sf-demo"}>
    <header className="sf-demo-header">
      <Link href="/" className="sf-demo-brand"><span>S</span><strong>SkillForge AI</strong></Link>
      <nav className="sf-demo-nav"><a href="#curriculum">Curriculum</a><a href="#questions">Question lab</a><a href="#journal">Journal</a><a href="#faq">FAQ</a></nav>
      <div className="sf-demo-actions"><span className="sf-demo-source-pill">1M source bank</span><button aria-label="Toggle demo theme" className="sf-demo-theme" onClick={() => setDark(value => !value)}>{dark ? <Sun size={16}/> : <Moon size={16}/>}</button></div>
    </header>

    <section className="sf-demo-hero">
      <div className="sf-demo-kicker">Interactive product preview · source-backed curriculum</div>
      <h1>Practise the <em>whole interview,</em> not just the syntax.</h1>
      <p>Explore a data-engineering interview workstation shaped by the reference recording: editorial hierarchy, a real interactive globe, deep curriculum, focused practice and explanations without turning the experience into another boxed SaaS dashboard.</p>
      <div className="sf-demo-hero-actions"><a className="sf-demo-primary" href="#curriculum">Explore the demo <ArrowRight size={15}/></a><Link className="sf-demo-secondary" href="/signup">Open full workspace</Link></div>
      <div className="sf-demo-proof">1,000,000 source rows · 15 subject files · 28 fields · 0 exact duplicate statements · parameterized concept families</div>
    </section>

    <section className="sf-demo-globe-wrap" aria-label="Interactive global practice visualization">
      <div className="sf-demo-globe-label"><span>GLOBAL PRACTICE</span><strong>Drag the globe. The geography is real; learner locations are never fabricated.</strong></div>
      <RotatingGlobe/>
    </section>

    <section id="curriculum" className="sf-demo-section">
      <div className="sf-demo-section-heading"><div><div className="sf-demo-kicker">Curriculum explorer</div><h2>Choose a domain and inspect the source coverage.</h2></div><p>The uploaded 1M-v1 manifest allocates the corpus across 15 subject files. This explorer uses those exact subject-level row counts, while keeping the full Parquet source outside the browser bundle.</p></div>
      <div className="sf-demo-curriculum-grid">
        <div className="sf-demo-subject-list">{subjects.map(subject => <button key={subject.id} className={selectedSubject.id === subject.id ? "active" : ""} onClick={() => setSelectedSubject(subject)}><span>{subject.label}</span><strong>{subject.count.toLocaleString()}</strong></button>)}</div>
        <article className="sf-demo-subject-detail"><div className="sf-demo-detail-top"><span>{selectedSubject.label}</span><span>{percent(selectedSubject.count)} of source rows</span></div><strong className="sf-demo-big-number">{selectedSubject.count.toLocaleString()}</strong><p>{selectedSubject.description}</p><div className="sf-demo-progress"><i style={{ width: percent(selectedSubject.count) }}/></div><div className="sf-demo-detail-meta"><span><Check size={14}/>Validated manifest allocation</span><span><Database size={14}/>Parquet source family</span></div></article>
      </div>
      <div className="sf-demo-validation-strip"><div><strong>100K</strong><span>smaller validated bank</span></div><div><strong>1M</strong><span>expanded parameterized bank</span></div><div><strong>15</strong><span>subjects in both manifests</span></div><div><strong>0</strong><span>exact duplicate statements reported</span></div></div>
    </section>

    <section id="questions" className="sf-demo-section sf-demo-question-section">
      <div className="sf-demo-section-heading"><div><div className="sf-demo-kicker">Question lab</div><h2>Search the interview by problem, not by page.</h2></div><p>Representative prompts below are drawn from the uploaded generator families and existing governed SkillForge source records. The demo keeps the interaction fast while the production path loads full records from the database.</p></div>
      <div className="sf-demo-question-toolbar"><label><Search size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search SQL, Snowflake, RAG, skew, system design…"/></label><div className="sf-demo-difficulty">{(["All","Easy","Medium","Hard"] as const).map(item => <button key={item} className={difficulty === item ? "active" : ""} onClick={() => setDifficulty(item)}>{item}</button>)}</div></div>
      <div className="sf-demo-question-grid">
        <div className="sf-demo-question-list">{filtered.length ? filtered.map(question => <button key={question.id} className={selectedQuestion.id === question.id ? "active" : ""} onClick={() => { setSelectedQuestion(question); setShowApproach(false); }}><span className="sf-demo-question-id">{question.id}</span><strong>{question.title}</strong><div><span>{question.subject}</span><span>{question.difficulty}</span></div></button>) : <div className="sf-demo-empty">No representative demo question matches that search.</div>}</div>
        <article className="sf-demo-question-preview"><div className="sf-demo-preview-meta"><span>{selectedQuestion.id}</span><span>{selectedQuestion.signal}</span></div><h3>{selectedQuestion.title}</h3><p>{selectedQuestion.prompt}</p><div className="sf-demo-preview-actions"><button onClick={() => setShowApproach(value => !value)}>{showApproach ? "Hide approach" : "Reveal approach"}</button><Link href="/login">Open in workspace <ArrowRight size={14}/></Link></div>{showApproach && <div className="sf-demo-approach"><Sparkles size={16}/><div><strong>Expected reasoning</strong><p>{selectedQuestion.approach}</p></div></div>}</article>
      </div>
    </section>

    <section className="sf-demo-section sf-demo-review-section">
      <div className="sf-demo-section-heading"><div><div className="sf-demo-kicker">Scenario review</div><h2>Write the architecture answer, then inspect the reasoning gaps.</h2></div><p>This public demo uses a transparent deterministic rubric so it works without pretending an AI model call happened. In the full workspace, this surface can call the configured explanation/review function.</p></div>
      <div className="sf-demo-review-grid">
        <article className="sf-demo-scenario"><div className="sf-demo-scenario-icon"><Target size={18}/></div><small>SNOWFLAKE · STAFF-LEVEL SCENARIO</small><h3>BI and ELT workloads contend on the same virtual warehouse.</h3><p>Propose the architecture, rollout, tradeoffs, recovery path and before/after evidence you would use to prove the remediation works.</p><ul><li>Preserve governed shared data.</li><li>Reduce queue time without uncontrolled credits.</li><li>Make rollback and observability explicit.</li><li>Explain what evidence you would inspect.</li></ul></article>
        <div className="sf-demo-answer"><textarea value={answer} onChange={event => { setAnswer(event.target.value); setReview(null); }} placeholder="Describe your architecture, tradeoffs, failure handling, governance and validation evidence…"/><div className="sf-demo-answer-footer"><span>{answer.length} characters</span><button onClick={reviewAnswer}>Review structure <Sparkles size={14}/></button></div>{review && <div className="sf-demo-rubric"><div className="sf-demo-rubric-score"><strong>{review.score}</strong><span>/100 demo rubric</span></div><div><p>{review.passed.length ? `Detected: ${review.passed.join(", ")}.` : "No rubric signals detected yet."}</p><p>{review.missing.length ? `Strengthen: ${review.missing.join(", ")}.` : "All rubric dimensions are represented."}</p></div></div>}</div>
      </div>
    </section>

    <section id="journal" className="sf-demo-section sf-demo-journal-section">
      <div className="sf-demo-section-heading"><div><div className="sf-demo-kicker">SkillForge Journal</div><h2>Technical depth should feel editorial, not buried in a dashboard.</h2></div><p>The reference recording uses an article-led journal to create depth between practice sessions. SkillForge follows that information hierarchy while using original content, branding and colors.</p></div>
      <div className="sf-demo-journal-grid">{journal.map(([eyebrow,title,body]) => <article key={title}><BookOpen size={17}/><small>{eyebrow}</small><h3>{title}</h3><p>{body}</p><span>Read field note ↗</span></article>)}</div>
    </section>

    <section id="faq" className="sf-demo-section sf-demo-faq-section">
      <div className="sf-demo-section-heading"><div><div className="sf-demo-kicker">Frequently asked questions</div><h2>What this demo does—and what it does not pretend to do.</h2></div></div>
      <div className="sf-demo-faq">{faqs.map(([question,answer]) => <details key={question}><summary><span>{question}</span><ChevronDown size={16}/></summary><p>{answer}</p></details>)}</div>
    </section>

    <footer className="sf-demo-footer"><div><span className="sf-demo-brandmark">S</span><strong>SkillForge AI</strong></div><p>Interactive preview · data engineering interview preparation · original visual system inspired by the supplied interaction reference.</p><div><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/signup">Create account</Link></div></footer>
  </main>;
}
