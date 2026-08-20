"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Database, Filter, Search } from "lucide-react";
import { demoQuestions, type DemoQuestion } from "@/lib/demo-data";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { DifficultyBadge, EmptyState, LoadingSkeleton, PageHeader, TopicBadge } from "./primitives";

type LiveQuestion = {
  id: string;
  public_id: string;
  title: string;
  difficulty: "Easy" | "Medium" | "Hard";
  question_type: string;
  primary_language: string;
  source_name: string | null;
  status: string;
  topics: { name: string; slug: string } | Array<{ name: string; slug: string }> | null;
};

type TopicRow = { id: string; name: string; slug: string };
type SourceMode = "loading" | "supabase" | "demo" | "error";
const PAGE_SIZE = 50;

function configured() {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

function topicName(row: LiveQuestion) {
  if (Array.isArray(row.topics)) return row.topics[0]?.name ?? "General";
  return row.topics?.name ?? "General";
}

export function LiveQuestionBrowser({ openDemoQuestion }: { openDemoQuestion: (question: DemoQuestion) => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("All");
  const [difficulty, setDifficulty] = useState("All");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState<LiveQuestion[]>([]);
  const [topics, setTopics] = useState<TopicRow[]>([]);
  const [count, setCount] = useState(0);
  const [mode, setMode] = useState<SourceMode>(configured() ? "loading" : "demo");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!configured()) return;
    const supabase = createSupabaseBrowserClient();
    supabase.from("topics").select("id,name,slug").order("sort_order").order("name").then(({ data }) => {
      if (data) setTopics(data as TopicRow[]);
    });
  }, []);

  useEffect(() => {
    if (!configured()) {
      setMode("demo");
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setMode("loading");
      setError("");
      try {
        const supabase = createSupabaseBrowserClient();
        let request = supabase
          .from("questions")
          .select("id,public_id,title,difficulty,question_type,primary_language,source_name,status,topics(name,slug)", { count: "exact" })
          .order("public_id", { ascending: true })
          .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);

        if (difficulty !== "All") request = request.eq("difficulty", difficulty);
        if (topic !== "All") {
          const topicId = topics.find(item => item.name === topic)?.id;
          if (topicId) request = request.eq("topic_id", topicId);
        }
        const trimmed = query.trim();
        if (trimmed) {
          if (/^[a-z]{2,12}[-_]/i.test(trimmed)) request = request.ilike("public_id", `%${trimmed}%`);
          else request = request.textSearch("search_document", trimmed, { type: "websearch", config: "english" });
        }

        const { data, error: fetchError, count: total } = await request;
        if (fetchError) throw fetchError;
        if (cancelled) return;
        setRows((data ?? []) as unknown as LiveQuestion[]);
        setCount(total ?? 0);
        setMode("supabase");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unable to load Supabase questions");
        setMode("error");
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, topic, difficulty, page, topics]);

  useEffect(() => { setPage(0); }, [query, topic, difficulty]);

  const demoRows = useMemo(() => demoQuestions.filter(item =>
    (topic === "All" || item.topic === topic) &&
    (difficulty === "All" || item.difficulty === difficulty) &&
    `${item.id} ${item.title} ${item.description} ${item.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase())
  ), [query, topic, difficulty]);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const topicOptions = mode === "demo"
    ? Array.from(new Set(demoQuestions.map(item => item.topic))).sort()
    : topics.map(item => item.name);

  return <section>
    <PageHeader
      eyebrow={mode === "supabase" ? `${count.toLocaleString()} accessible Supabase records` : "24,800 normalized records · source-backed demo subset"}
      title="Question Bank"
      description={mode === "supabase"
        ? "This browser is querying the governed Supabase question table with RLS, server-side filtering and pagination."
        : "Configure Supabase and import reviewed records to switch this browser from the source-backed seed to the governed live corpus."}
    />

    <div className="sf-filter-bar">
      <div className="sf-search-input"><Search size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search title/body or enter an ID…"/></div>
      <select value={topic} onChange={event => setTopic(event.target.value)}><option value="All">All topics</option>{topicOptions.map(item => <option key={item}>{item}</option>)}</select>
      <select value={difficulty} onChange={event => setDifficulty(event.target.value)}><option value="All">All difficulty</option><option>Easy</option><option>Medium</option><option>Hard</option></select>
      <button className="sf-filter-button" type="button"><Filter size={15}/>{mode === "supabase" ? "Live filters" : "Demo filters"}</button>
    </div>

    {mode === "loading" && <div className="sf-pad"><LoadingSkeleton lines={7}/></div>}
    {mode === "error" && <div className="sf-inline-error">Supabase query failed: {error}. The application has not silently substituted demo results.</div>}

    {mode === "supabase" && rows.length === 0 && <EmptyState title="No accessible questions match" description="If the corpus was imported in rights-review status, a normal learner account will not see those records until a reviewer publishes them."/>}
    {mode === "supabase" && rows.length > 0 && <>
      <div className="sf-table-wrap"><table className="sf-question-table"><thead><tr><th>ID</th><th>Problem</th><th>Difficulty</th><th>Topic</th><th>Type</th><th>Source</th><th>Status</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} onClick={() => router.push(`/questions/${encodeURIComponent(row.public_id)}`)}><td className="sf-mono-id">{row.public_id}</td><td><b>{row.title}</b><small>{row.primary_language}</small></td><td><DifficultyBadge value={row.difficulty}/></td><td><TopicBadge>{topicName(row)}</TopicBadge></td><td>{row.question_type}</td><td>{row.source_name ?? "—"}</td><td><span className="sf-match-score">{row.status}</span></td></tr>)}</tbody></table></div>
      <div className="sf-inline-actions sf-section-spaced"><button className="sf-filter-button" disabled={page === 0} onClick={() => setPage(value => Math.max(0, value - 1))}><ChevronLeft size={15}/>Previous</button><span className="sf-meta-stat">Page {page + 1} of {totalPages} · {count.toLocaleString()} records</span><button className="sf-filter-button" disabled={page + 1 >= totalPages} onClick={() => setPage(value => value + 1)}>Next<ChevronRight size={15}/></button></div>
    </>}

    {mode === "demo" && <>
      <div className="sf-health-line"><Database size={16}/>Supabase is not configured in this browser environment; showing only the six checked-in source-backed demo records.</div>
      {demoRows.length === 0 ? <EmptyState title="No demo questions match" description="The full corpus is intentionally not bundled in the browser."/> : <div className="sf-table-wrap"><table className="sf-question-table"><thead><tr><th>ID</th><th>Problem</th><th>Difficulty</th><th>Topic</th><th>Type</th><th>Source</th></tr></thead><tbody>{demoRows.map(row => <tr key={row.id} onClick={() => openDemoQuestion(row)}><td className="sf-mono-id">{row.id}</td><td><b>{row.title}</b><small>{row.bank}</small></td><td><DifficultyBadge value={row.difficulty}/></td><td><TopicBadge>{row.topic}</TopicBadge></td><td>{row.type}</td><td><span className="sf-match-score">verified seed</span></td></tr>)}</tbody></table></div>}
    </>}
  </section>;
}
