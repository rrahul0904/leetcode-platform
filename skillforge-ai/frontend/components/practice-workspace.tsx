"use client";

import { useEffect, useMemo, useState } from "react";
import { BrainCircuit, ChevronLeft, Lightbulb, Play, RotateCcw, Send, Sparkles } from "lucide-react";
import type { DemoQuestion } from "@/lib/demo-data";
import { runCode } from "@/lib/api";
import { DifficultyBadge, ErrorState, PrimaryButton, SecondaryButton, SuccessState, TopicBadge } from "./primitives";
import { MonacoCodeEditor } from "./monaco-code-editor";

function starter(language: "python" | "sql") {
  return language === "python"
    ? "def solve(values):\n    # Write your solution\n    return values\n\nprint(solve([3, 12, 18, 20]))\n"
    : "SELECT carrier_id,\n       SUM(duration) AS total_duration,\n       COUNT(*) AS row_count\nFROM facts\nWHERE status = 'completed'\nGROUP BY carrier_id;";
}

export function PracticeWorkspace({ question, mode, onBack }: { question: DemoQuestion; mode: "python" | "sql"; onBack: () => void }) {
  const storageKey = useMemo(() => `skillforge:draft:${question.id}:${mode}`, [question.id, mode]);
  const [code, setCode] = useState(starter(mode));
  const [tab, setTab] = useState<"problem" | "solution" | "discussion">("problem");
  const [runState, setRunState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [output, setOutput] = useState("");
  const [runtime, setRuntime] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [tutorOpen, setTutorOpen] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey);
    if (saved) setCode(saved);
  }, [storageKey]);
  useEffect(() => { window.localStorage.setItem(storageKey, code); }, [code, storageKey]);

  async function execute(submit = false) {
    setRunState("running"); setError(""); setOutput(""); setRuntime(null);
    try {
      const result = await runCode(mode, code);
      setOutput(result.output); setRuntime(result.runtime_ms); setRunState("success");
      if (submit) window.localStorage.setItem(`skillforge:accepted:${question.id}`, "true");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
      setRunState("error");
    }
  }

  return <div className="sf-workspace-page">
    <div className="sf-workspace-toolbar"><button className="sf-back" onClick={onBack}><ChevronLeft size={15}/>Back to Question Bank</button><div className="sf-workspace-actions"><SecondaryButton onClick={() => setCode(starter(mode))}><RotateCcw size={14}/>Reset</SecondaryButton><SecondaryButton disabled={runState === "running"} onClick={() => execute(false)}><Play size={14}/>Run</SecondaryButton><PrimaryButton disabled={runState === "running"} onClick={() => execute(true)}><Send size={14}/>Submit</PrimaryButton></div></div>
    <div className="sf-workspace-grid">
      <section className="sf-workspace-panel sf-problem-panel">
        <header className="sf-workspace-panel-head"><div><span className="sf-mono-id">{question.id}</span><h2>{question.title}</h2></div><DifficultyBadge value={question.difficulty}/></header>
        <div className="sf-problem-meta"><TopicBadge>{question.topic}</TopicBadge>{question.tags.slice(0,3).map(tag => <TopicBadge key={tag}>{tag}</TopicBadge>)}<span className="sf-meta-stat">15–25 min</span><span className="sf-meta-stat">78% success</span></div>
        <div className="sf-tabs"><button className={tab === "problem" ? "active" : ""} onClick={() => setTab("problem")}>Problem</button><button className={tab === "solution" ? "active" : ""} onClick={() => setTab("solution")}>Solution</button><button className={tab === "discussion" ? "active" : ""} onClick={() => setTab("discussion")}>Discussion</button><button className="sf-ai-tab" onClick={() => setTutorOpen(v => !v)}><Sparkles size={13}/>AI Tutor</button></div>
        <div className="sf-reading-pane"><div className="sf-markdownish">{tab === "problem" ? question.description : tab === "solution" ? question.explanation : "Discussion will surface community notes and reviewer-approved explanations. This demo keeps discussion read-only."}</div><details className="sf-hint"><summary><Lightbulb size={14}/>Hint</summary><p>Identify the governing invariant first, then choose the smallest data structure or SQL operation that satisfies it.</p></details><div className="sf-related"><strong>Related questions</strong><span>Window frames · workload isolation · aggregation edge cases</span></div></div>
      </section>
      <section className="sf-workspace-panel sf-editor-panel">
        <header className="sf-editor-head"><div><span className="sf-editor-language">{mode === "python" ? "Python 3.13" : "PostgreSQL 18"}</span><span className="sf-editor-runtime">Monaco · autosaved</span></div><div className="sf-editor-head-actions"><SecondaryButton onClick={() => setTutorOpen(v => !v)}><BrainCircuit size={14}/>AI Hint</SecondaryButton></div></header>
        <MonacoCodeEditor language={mode} value={code} onChange={setCode}/>
        <div className="sf-result-tabs"><button className="active">Test Cases</button><button>Output</button><button>Console</button></div>
        <div className="sf-run-result">
          {runState === "idle" && <div className="sf-muted">Run your code against the configured SkillForge runner.</div>}
          {runState === "running" && <div className="sf-running-line"><span className="sf-pulse"/>Executing isolated demo runner…</div>}
          {runState === "success" && <><SuccessState title="Execution completed" description={`Runtime ${runtime ?? 0} ms`}/><pre className="sf-output-pre">{output}</pre></>}
          {runState === "error" && <ErrorState title="Execution failed" description="The runner rejected or could not execute this submission." technical={error} onRetry={() => execute(false)}/>} 
        </div>
      </section>
      {tutorOpen && <aside className="sf-tutor-drawer"><div className="sf-tutor-head"><div><span className="sf-eyebrow">Contextual AI Tutor</span><h3>Work through this problem</h3></div><button onClick={() => setTutorOpen(false)}>×</button></div><div className="sf-tutor-actions"><button>Explain question</button><button>Give hint</button><button>Create simpler example</button><button>Explain solution</button></div><div className="sf-tutor-message"><Sparkles size={16}/><div><strong>Suggested focus</strong><p>Start by stating the invariant in one sentence. I’ll help with the next step without revealing the full answer unless you ask.</p></div></div><div className="sf-ai-disclaimer">AI can make mistakes. Verify critical technical details.</div></aside>}
    </div>
  </div>;
}
