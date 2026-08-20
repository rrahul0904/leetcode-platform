"use client";

import { useMemo, useState } from "react";
import { ArrowRight, BookOpenCheck, CheckCircle2, ChevronRight, Filter, RefreshCcw, Search, Sparkles, UploadCloud } from "lucide-react";
import { demoQuestions, type DemoQuestion } from "@/lib/demo-data";
import { requestAIExplanation, requestSemanticSearch, type SearchMode, type SemanticSearchHit } from "@/lib/api";
import { AppShell, type View } from "./app-shell";
import { PracticeWorkspace } from "./practice-workspace";
import { DifficultyBadge, EmptyState, GradientCard, LoadingSkeleton, MetricCard, PageHeader, PrimaryButton, SecondaryButton, TopicBadge } from "./primitives";

export function SkillForgeRedesign({ initialView }: { initialView: View }) {
  const [view, setView] = useState<View>(initialView);
  const [selected, setSelected] = useState<DemoQuestion | null>(null);
  function openQuestion(q: DemoQuestion) {
    setSelected(q);
    if (q.language === "python") setView("python");
    else if (q.language === "sql") setView("sql");
    else if (q.type.toLowerCase().includes("mcq")) setView("quiz");
    else setView("scenarios");
  }
  if ((view === "python" || view === "sql") && selected) {
    return <AppShell view={view} setView={setView}><PracticeWorkspace question={selected} mode={view} onBack={() => { setSelected(null); setView("questions"); }}/></AppShell>;
  }
  return <AppShell view={view} setView={setView}>
    {view === "dashboard" && <Dashboard setView={setView} openQuestion={openQuestion}/>} 
    {view === "questions" && <QuestionBrowser openQuestion={openQuestion}/>} 
    {(view === "python" || view === "sql") && <PracticeLanding mode={view} openQuestion={openQuestion}/>} 
    {view === "quiz" && <MCQArena question={selected ?? demoQuestions.find(q => q.type === "MCQ")!}/>} 
    {view === "scenarios" && <ScenarioExperience question={selected ?? demoQuestions.find(q => q.id === "ENT-0001")!}/>} 
    {view === "search" && <SemanticSearch openQuestion={openQuestion}/>} 
    {view === "progress" && <ProgressPage/>} 
    {view === "admin" && <AdminCenter/>} 
    {view === "bookmarks" && <Bookmarks openQuestion={openQuestion}/>} 
    {view === "paths" && <LearningPaths setView={setView}/>} 
  </AppShell>;
}

function Dashboard({ setView, openQuestion }: { setView: (view: View) => void; openQuestion: (q: DemoQuestion) => void }) {
  const skills = [["SQL",84],["Python",77],["Snowflake",69],["PySpark",64],["System Design",58],["Cloud",61]] as const;
  return <section>
    <PageHeader eyebrow="SkillForge Command Center" title="Train for the interview you actually want." description="A source-backed technical learning command center spanning coding, data engineering, cloud, system design, certification preparation and AI architecture."/>
    <div className="sf-dashboard-hero-grid"><GradientCard className="sf-hero-card"><div className="sf-hero-copy"><TopicBadge>Current path · Senior Data Engineer</TopicBadge><h2>Welcome back. Your next best session is ready.</h2><p>Focus on SQL window functions, Snowflake workload isolation and one architecture scenario to improve your modeled readiness.</p><div className="sf-inline-actions"><PrimaryButton onClick={() => setView("questions")}>Continue Practice <ArrowRight size={15}/></PrimaryButton><SecondaryButton onClick={() => setView("progress")}>View Progress</SecondaryButton></div></div><div className="sf-readiness-ring"><div><strong>72%</strong><span>Readiness</span></div></div></GradientCard>
      <GradientCard glow="violet" className="sf-coach-card"><div className="sf-card-heading"><div><div className="sf-eyebrow sf-violet">AI Study Coach</div><h3>Today’s recommendation</h3></div><Sparkles className="sf-violet-icon"/></div><p>Your coding accuracy is strong, but architecture explanations lose points on tradeoffs and operational validation.</p><div className="sf-chip-row"><button>Explain weakest area</button><button>Build 45-min plan</button></div></GradientCard></div>
    <div className="sf-metric-grid"><MetricCard label="Normalized corpus" value="24,800" helper="22 source banks · import-ready"/><MetricCard label="Accuracy" value="81.4%" helper="demo readiness model" accent="emerald"/><MetricCard label="Completed" value="386" helper="demo progress state" accent="violet"/><MetricCard label="Streak" value="12d" helper="demo progress state" accent="amber"/></div>
    <div className="sf-dashboard-two"><GradientCard glow="none" className="sf-pad"><div className="sf-section-heading"><h2>Skill readiness</h2><span>demo model</span></div><div className="sf-skill-bars">{skills.map(([name,value]) => <div key={name} className="sf-skill-row"><span>{name}</span><div><i style={{ width: `${value}%` }}/></div><b>{value}</b></div>)}</div></GradientCard><GradientCard glow="none" className="sf-pad"><div className="sf-section-heading"><h2>Corpus intelligence</h2><span>schema + ingestion contracts</span></div><div className="sf-corpus-stats"><div><small>Normalized records</small><strong>24.8k</strong><span>source-backed inventory</span></div><div><small>Scenarios</small><strong>1,800</strong><span>1,090 with code</span></div></div><div className="sf-health-line"><CheckCircle2 size={16}/>Hybrid search schema and Edge Function checked in</div></GradientCard></div>
    <div className="sf-section-heading sf-section-spaced"><h2>Recommended next</h2><span>demo subset</span></div><div className="sf-recommend-grid">{demoQuestions.slice(2,5).map(q => <button key={q.id} className="sf-question-card" onClick={() => openQuestion(q)}><div><DifficultyBadge value={q.difficulty}/><TopicBadge>{q.topic}</TopicBadge></div><h3>{q.title}</h3><p>{q.language === "text" ? "15–25 min · architecture reasoning" : "10–15 min · coding practice"}</p><ChevronRight size={16}/></button>)}</div>
  </section>;
}

function QuestionBrowser({ openQuestion }: { openQuestion: (q: DemoQuestion) => void }) {
  const [query,setQuery] = useState(""); const [topic,setTopic] = useState("All"); const [difficulty,setDifficulty] = useState("All"); const [viewMode,setViewMode] = useState<"table"|"cards">("table");
  const filtered = useMemo(() => demoQuestions.filter(q => (topic === "All" || q.topic === topic) && (difficulty === "All" || q.difficulty === difficulty) && (`${q.id} ${q.title} ${q.description} ${q.tags.join(" ")}`).toLowerCase().includes(query.toLowerCase())), [query,topic,difficulty]);
  return <section><PageHeader eyebrow="24,800 normalized records · demo subset loaded" title="Question Bank" description="Search and open the source-backed demo subset now; the full normalized corpus is designed to load through Supabase rather than ship inside the frontend bundle." actions={<div className="sf-view-toggle"><button className={viewMode === "table" ? "active" : ""} onClick={() => setViewMode("table")}>Table</button><button className={viewMode === "cards" ? "active" : ""} onClick={() => setViewMode("cards")}>Cards</button></div>}/><div className="sf-filter-bar"><div className="sf-search-input"><Search size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search title, body, tags…"/></div><select value={topic} onChange={e => setTopic(e.target.value)}><option value="All">All topics</option><option>Python</option><option>SQL</option><option>Snowflake</option></select><select value={difficulty} onChange={e => setDifficulty(e.target.value)}><option value="All">All difficulty</option><option>Easy</option><option>Medium</option><option>Hard</option></select><button className="sf-filter-button"><Filter size={15}/>More filters</button></div>{filtered.length === 0 ? <EmptyState title="No questions match those filters" description="Try clearing one filter or search for a broader concept."/> : viewMode === "table" ? <div className="sf-table-wrap"><table className="sf-question-table"><thead><tr><th>Status</th><th>ID</th><th>Problem</th><th>Difficulty</th><th>Topic</th><th>Type</th><th>Source</th></tr></thead><tbody>{filtered.map((q,index) => <tr key={q.id} onClick={() => openQuestion(q)}><td>{index % 2 ? "○" : "✓"}</td><td className="sf-mono-id">{q.id}</td><td><b>{q.title}</b><small>{q.bank}</small></td><td><DifficultyBadge value={q.difficulty}/></td><td>{q.topic}</td><td>{q.type}</td><td><span className="sf-match-score">verified seed</span></td></tr>)}</tbody></table></div> : <div className="sf-browser-card-grid">{filtered.map(q => <button key={q.id} className="sf-question-card" onClick={() => openQuestion(q)}><div><DifficultyBadge value={q.difficulty}/><TopicBadge>{q.topic}</TopicBadge></div><h3>{q.title}</h3><p className="sf-mono-id">{q.id}</p></button>)}</div>}</section>;
}

function PracticeLanding({ mode, openQuestion }: { mode: "python" | "sql"; openQuestion: (q: DemoQuestion) => void }) { const rows = demoQuestions.filter(q => q.language === mode); return <section><PageHeader eyebrow="Practice Lab" title={`${mode === "python" ? "Python" : "SQL"} workspace`} description="Choose a source-backed question to open the Monaco editor and FastAPI runner integration."/><div className="sf-browser-card-grid">{rows.map(q => <button key={q.id} className="sf-question-card" onClick={() => openQuestion(q)}><div><DifficultyBadge value={q.difficulty}/><TopicBadge>{q.topic}</TopicBadge></div><h3>{q.title}</h3><p>{q.id}</p></button>)}</div></section>; }

function MCQArena({ question }: { question: DemoQuestion }) { const [selected,setSelected] = useState<string|null>(null); const answer = "A"; const choices = [["A","Separate virtual warehouses for independent workloads"],["B","Increase retention settings even though recovery is unrelated"],["C","Rebuild downstream tables from scratch on every run"],["D","Use a single always-on warehouse for every workload"]]; return <section className="sf-narrow"><PageHeader eyebrow="Snowflake Advanced Architect" title="MCQ Arena" description="Immediate feedback and source-backed explanation for the checked-in demo question."/><div className="sf-quiz-progress"><i style={{ width: "40%" }}/><span>4 / 10</span></div><GradientCard glow="none" className="sf-pad sf-quiz-card"><div className="sf-quiz-top"><DifficultyBadge value={question.difficulty}/><TopicBadge>{question.topic}</TopicBadge></div><h2>{question.title}</h2><div className="sf-choice-list">{choices.map(([key,text]) => <button key={key} className={selected === key ? `sf-choice selected ${key === answer ? "correct" : "wrong"}` : selected && key === answer ? "sf-choice correct" : "sf-choice"} onClick={() => setSelected(key)}><span>{key}</span><b>{text}</b></button>)}</div>{selected && <div className="sf-explanation-panel"><strong>{selected === answer ? "Correct — workload isolation is the key." : "Not quite — compare the requirement to compute isolation."}</strong><p>{question.explanation}</p><details><summary>Why the other options are wrong</summary><p>Retention, rebuild cadence and a single shared warehouse do not isolate compute contention.</p></details></div>}<div className="sf-quiz-actions"><SecondaryButton>Save for review</SecondaryButton><PrimaryButton>Next Question <ArrowRight size={14}/></PrimaryButton></div></GradientCard></section>; }

function ScenarioExperience({ question }: { question: DemoQuestion }) {
  const [answer, setAnswer] = useState("");
  const [review, setReview] = useState<"idle"|"loading"|"done"|"error">("idle");
  const [feedback, setFeedback] = useState("");
  async function runReview() {
    if (!answer.trim()) { setFeedback("Write an answer before requesting review."); setReview("error"); return; }
    setReview("loading"); setFeedback("");
    try {
      const result = await requestAIExplanation({ questionId: question.id, question: `${question.title}\n\n${question.description}`, answer, focus: "review" });
      setFeedback(result.explanation || "The AI provider returned no review text.");
      setReview("done");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "AI review failed");
      setReview("error");
    }
  }
  return <section><PageHeader eyebrow="Enterprise Data Engineering Interview" title="Architecture Scenario" description="Business context, constraints, structured answer space and live AI review when the provider is configured."/><div className="sf-scenario-grid"><GradientCard glow="none" className="sf-pad"><div className="sf-scenario-heading"><div><span className="sf-mono-id">{question.id}</span><h2>{question.title}</h2></div><DifficultyBadge value="Expert"/></div><div className="sf-markdownish">{question.description}</div><h3>Requirements checklist</h3><ul className="sf-checklist"><li>Isolate interactive BI from heavy ELT.</li><li>Preserve governed shared data.</li><li>Reduce queue time without uncontrolled cost.</li><li>Define before/after operational evidence.</li></ul><textarea className="sf-answer-area" value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Describe architecture, investigation steps, tradeoffs, rollout and validation…"/><div className="sf-inline-actions"><PrimaryButton disabled={review === "loading"} onClick={runReview}><Sparkles size={14}/>AI Review</PrimaryButton><SecondaryButton>Suggested Solution</SecondaryButton><SecondaryButton>Tradeoffs</SecondaryButton></div>{review === "loading" && <LoadingSkeleton/>}{review === "done" && <div className="sf-ai-review"><strong>AI review</strong><p>{feedback}</p></div>}{review === "error" && <div className="sf-inline-error">{feedback}</div>}</GradientCard><GradientCard glow="violet" className="sf-pad"><div className="sf-section-heading"><h2>Architecture sketch</h2><span>guided reference view</span></div><div className="sf-diagram"><span className="node n1">Salesforce + SAP</span><span className="node n2">Snowflake Storage</span><span className="node n3">BI Warehouse</span><span className="node n4">ELT Warehouse</span></div><div className="sf-health-line"><CheckCircle2 size={16}/>Target pattern: shared storage + workload-specific compute</div></GradientCard></div></section>;
}

function SemanticSearch({ openQuestion }: { openQuestion: (q: DemoQuestion) => void }) {
  const [query,setQuery] = useState("Find hard Snowflake workload isolation and cost optimization scenarios");
  const [mode,setMode] = useState<"Keyword"|"Semantic"|"Hybrid">("Hybrid");
  const [loading,setLoading] = useState(false);
  const [results,setResults] = useState<DemoQuestion[]>(demoQuestions.filter(q => q.topic === "Snowflake"));
  const [remoteHits,setRemoteHits] = useState<SemanticSearchHit[]>([]);
  const [executedMode,setExecutedMode] = useState("");
  const [warning,setWarning] = useState("");
  const [error,setError] = useState("");
  async function search() {
    setLoading(true); setError(""); setWarning("");
    try {
      const remote = await requestSemanticSearch(query, mode.toLowerCase() as SearchMode);
      if (remote) {
        setRemoteHits(remote.results ?? []);
        setExecutedMode(remote.executed_mode);
        setWarning(remote.warning ?? "");
        if (remote.results?.length) {
          const ids = new Set(remote.results.map(hit => hit.public_id));
          setResults(demoQuestions.filter(q => ids.has(q.id)));
          return;
        }
      }
      setRemoteHits([]);
      setExecutedMode("local-demo-fallback");
      const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      setResults([...demoQuestions].sort((a,b) => terms.filter(t => `${b.title} ${b.description}`.toLowerCase().includes(t)).length - terms.filter(t => `${a.title} ${a.description}`.toLowerCase().includes(t)).length).slice(0,4));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally { setLoading(false); }
  }
  return <section><GradientCard glow="violet" className="sf-semantic-hero"><div className="sf-eyebrow sf-violet">AI-native retrieval</div><h1>Search by meaning, not just keywords.</h1><p>Hybrid mode calls the Supabase Edge Function, generates an embedding when a provider is configured, and falls back to full-text search when it is not.</p><div className="sf-semantic-prompts">{["Hard Snowflake cost optimization","SQL retention using window functions","PySpark skew-handling scenarios"].map(p => <button key={p} onClick={() => setQuery(p)}>{p}</button>)}</div><div className="sf-semantic-input"><Sparkles size={18}/><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && search()}/><PrimaryButton onClick={search}>Search</PrimaryButton></div><div className="sf-mode-toggle">{(["Keyword","Semantic","Hybrid"] as const).map(item => <button className={mode === item ? "active" : ""} key={item} onClick={() => setMode(item)}>{item}</button>)}</div></GradientCard>{executedMode && <div className="sf-health-line"><CheckCircle2 size={16}/>Executed mode: {executedMode}</div>}{warning && <div className="sf-inline-error">{warning}</div>}{error && <div className="sf-inline-error">{error}</div>}{loading ? <GradientCard glow="none" className="sf-pad"><div className="sf-embedding-status"><span className="sf-pulse"/>Searching configured retrieval backend…</div><LoadingSkeleton lines={4}/></GradientCard> : remoteHits.length > 0 ? <div className="sf-semantic-results">{remoteHits.map((hit,index) => { const demo = demoQuestions.find(q => q.id === hit.public_id); const score = Math.max(0, Math.min(100, Math.round(Number(hit.score || 0) * 100))); return <button key={hit.question_id ?? hit.public_id} onClick={() => demo && openQuestion(demo)} disabled={!demo}><span className="sf-match-score">{score}% score</span><div><DifficultyBadge value={hit.difficulty}/><TopicBadge>{demo?.topic ?? "Source corpus"}</TopicBadge></div><h3>{hit.title}</h3><p>{demo ? "Open the checked-in demo record." : `Result ${index + 1} from Supabase; full detail route is the next ingestion-backed slice.`}</p></button>; })}</div> : <div className="sf-semantic-results">{results.map((q,index) => <button key={q.id} onClick={() => openQuestion(q)}><span className="sf-match-score">demo rank {index + 1}</span><div><DifficultyBadge value={q.difficulty}/><TopicBadge>{q.topic}</TopicBadge></div><h3>{q.title}</h3><p>Local demo fallback matched {q.tags.slice(0,3).join(", ")}.</p></button>)}</div>}</section>;
}

function ProgressPage() { return <section><PageHeader eyebrow="Adaptive learning intelligence" title="Progress & readiness" description="The current UI demonstrates the progress model. Supabase persistence is the next slice for attempts, mastery and spaced review."/><div className="sf-metric-grid"><MetricCard label="Overall readiness" value="72%" helper="demo model"/><MetricCard label="Attempts" value="512" helper="demo state" accent="violet"/><MetricCard label="Accuracy" value="81%" helper="demo state" accent="emerald"/><MetricCard label="Review queue" value="27" helper="demo state" accent="amber"/></div></section>; }

function AdminCenter() { const [step,setStep] = useState(1); const steps = [["Upload","private Supabase Storage"],["Validate","schema + duplicate checks"],["Approve","reviewer gate"],["Embed","pgvector job"]]; return <section><PageHeader eyebrow="Enterprise content operations" title="Admin Intelligence Center" description="The database, role, storage and import contracts are checked in. This screen visualizes the governed pipeline while worker-backed processing remains to be connected."/><GradientCard glow="none" className="sf-pad"><div className="sf-pipeline">{steps.map(([title,desc],index) => <div key={title} className={index < step ? "done" : index === step ? "active" : ""}><span>{index + 1}</span><b>{title}</b><small>{desc}</small></div>)}</div><div className="sf-inline-actions"><PrimaryButton onClick={() => setStep(value => Math.min(3, value + 1))}><UploadCloud size={14}/>Advance demo pipeline</PrimaryButton><SecondaryButton><RefreshCcw size={14}/>Retry failed rows</SecondaryButton></div></GradientCard><div className="sf-metric-grid sf-section-spaced"><MetricCard label="Normalized records" value="24.8k" helper="source inventory" accent="emerald"/><MetricCard label="Review workflow" value="RLS" helper="role-gated" accent="violet"/><MetricCard label="Storage" value="Private" helper="50 MB/file policies" accent="amber"/><MetricCard label="Vector schema" value="HNSW" helper="1536 dimensions"/></div></section>; }

function Bookmarks({ openQuestion }: { openQuestion: (q: DemoQuestion) => void }) { const rows = demoQuestions.slice(0,3); return <section><PageHeader eyebrow="Saved for later" title="Bookmarks" description="The UI currently uses the demo subset; the Supabase bookmarks table and user-scoped RLS policy are checked in."/><div className="sf-browser-card-grid">{rows.map(q => <button key={q.id} className="sf-question-card" onClick={() => openQuestion(q)}><DifficultyBadge value={q.difficulty}/><h3>{q.title}</h3><p>{q.id}</p></button>)}</div></section>; }
function LearningPaths({ setView }: { setView: (view: View) => void }) { return <section><PageHeader eyebrow="Role-aligned preparation" title="Learning Paths" description="Structured sequences combine coding, architecture, scenarios and spaced review."/><div className="sf-browser-card-grid">{[["Senior Data Engineer","SQL → Python → Pipelines → System Design","42%"],["Snowflake Architect","Platform → Performance → Security → Cost","28%"],["AI Data Architect","RAG → Vector Search → Agents → Governance","12%"]].map(([title,body,progress]) => <button key={title} className="sf-question-card" onClick={() => setView("questions")}><BookOpenCheck/><h3>{title}</h3><p>{body}</p><div className="sf-path-progress"><i style={{ width: progress }}/></div><span>{progress} demo progress</span></button>)}</div></section>; }
