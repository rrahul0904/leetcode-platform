"use client";

import {
  Braces,
  CheckCircle2,
  Database,
  Maximize2,
  Minimize2,
  Play,
  RotateCcw,
  Send,
  TerminalSquare,
} from "lucide-react";
import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

export type CodingLanguage = "python" | "sql";
export type CodingPadResult = {
  status: "idle" | "queued" | "running" | "passed" | "failed";
  message: string;
  runtimeMs?: number;
  rows?: Array<Record<string, unknown>>;
};

type InteractiveCodingPadProps = {
  questionKey: string;
  language: CodingLanguage;
  initialSource: string;
  executionEnabled?: boolean;
  schema?: string;
  onRun?: (source: string, customInput: string) => Promise<CodingPadResult>;
  onSubmit?: (source: string) => Promise<CodingPadResult>;
};

const languageLabel: Record<CodingLanguage, string> = {
  python: "PYTHON 3.13",
  sql: "POSTGRESQL 18",
};

function lineNumbers(source: string) {
  return Array.from({ length: Math.max(1, source.split("\n").length) }, (_, index) => index + 1);
}

export function InteractiveCodingPad({
  questionKey,
  language,
  initialSource,
  executionEnabled = false,
  schema,
  onRun,
  onSubmit,
}: InteractiveCodingPadProps) {
  const storageKey = `rigor.coding-pad:${questionKey}:${language}`;
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const [source, setSource] = useState(initialSource);
  const [customInput, setCustomInput] = useState("");
  const [result, setResult] = useState<CodingPadResult>({ status: "idle", message: "Run your code to see results." });
  const [activePanel, setActivePanel] = useState<"tests" | "output" | "schema">("tests");
  const [fullscreen, setFullscreen] = useState(false);
  const [saved, setSaved] = useState(true);
  const numbers = useMemo(() => lineNumbers(source), [source]);

  useEffect(() => {
    const restored = window.localStorage.getItem(storageKey);
    queueMicrotask(() => setSource(restored ?? initialSource));
  }, [initialSource, storageKey]);

  useEffect(() => {
    setSaved(false);
    const timeout = window.setTimeout(() => {
      window.localStorage.setItem(storageKey, source);
      setSaved(true);
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [source, storageKey]);

  function insertText(text: string) {
    const editor = editorRef.current;
    if (!editor) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    setSource((value) => `${value.slice(0, start)}${text}${value.slice(end)}`);
    window.requestAnimationFrame(() => {
      editor.focus();
      editor.selectionStart = editor.selectionEnd = start + text.length;
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Tab") {
      event.preventDefault();
      insertText("    ");
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void run();
    }
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key === "Enter") {
      event.preventDefault();
      void submit();
    }
  }

  async function run() {
    if (!executionEnabled || !onRun) {
      setActivePanel("output");
      setResult({ status: "failed", message: "Execution is locked until this question has validated tests and a published runtime contract." });
      return;
    }
    setActivePanel("output");
    setResult({ status: "queued", message: "Execution queued…" });
    try {
      setResult({ status: "running", message: "Running in the isolated judge…" });
      setResult(await onRun(source, customInput));
    } catch {
      setResult({ status: "failed", message: "Execution could not be completed. Your draft remains saved." });
    }
  }

  async function submit() {
    if (!executionEnabled || !onSubmit) {
      setActivePanel("output");
      setResult({ status: "failed", message: "Submission is locked until hidden tests are validated and published." });
      return;
    }
    setActivePanel("output");
    setResult({ status: "queued", message: "Submission queued…" });
    try {
      setResult({ status: "running", message: "Evaluating public and hidden tests…" });
      setResult(await onSubmit(source));
    } catch {
      setResult({ status: "failed", message: "Submission could not be completed. Retry is safe." });
    }
  }

  function reset() {
    setSource(initialSource);
    setCustomInput("");
    setResult({ status: "idle", message: "Draft reset to the starter source." });
    window.localStorage.removeItem(storageKey);
  }

  return (
    <section className={`coding-pad ${fullscreen ? "coding-pad--fullscreen" : ""}`} aria-label={`${languageLabel[language]} coding pad`}>
      <header className="coding-pad__toolbar">
        <div>
          {language === "sql" ? <Database size={16} /> : <Braces size={16} />}
          <strong>{languageLabel[language]}</strong>
          <span>{saved ? "Saved" : "Saving…"}</span>
        </div>
        <div>
          <button type="button" onClick={reset} aria-label="Reset code"><RotateCcw size={15} /></button>
          <button type="button" onClick={() => setFullscreen((value) => !value)} aria-label={fullscreen ? "Exit full screen" : "Enter full screen"}>
            {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      </header>

      <div className="coding-pad__editor-shell">
        <pre className="coding-pad__lines" aria-hidden="true">{numbers.join("\n")}</pre>
        <textarea
          ref={editorRef}
          aria-label={`${languageLabel[language]} source code`}
          value={source}
          spellCheck={false}
          onChange={(event) => setSource(event.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>

      <nav className="coding-pad__tabs" aria-label="Coding pad panels">
        <button className={activePanel === "tests" ? "is-active" : ""} onClick={() => setActivePanel("tests")} type="button">Custom tests</button>
        <button className={activePanel === "output" ? "is-active" : ""} onClick={() => setActivePanel("output")} type="button">Output</button>
        {language === "sql" && <button className={activePanel === "schema" ? "is-active" : ""} onClick={() => setActivePanel("schema")} type="button">Schema</button>}
      </nav>

      <div className="coding-pad__panel">
        {activePanel === "tests" && (
          <textarea
            aria-label="Custom test input"
            placeholder={language === "sql" ? "Optional fixture or parameter notes" : "Enter custom JSON/string input"}
            value={customInput}
            onChange={(event) => setCustomInput(event.target.value)}
          />
        )}
        {activePanel === "schema" && <pre>{schema || "No schema is available for this question."}</pre>}
        {activePanel === "output" && (
          <div className={`coding-pad__result coding-pad__result--${result.status}`}>
            {result.status === "passed" ? <CheckCircle2 size={17} /> : <TerminalSquare size={17} />}
            <div>
              <strong>{result.status.toUpperCase()}</strong>
              <p>{result.message}</p>
              {typeof result.runtimeMs === "number" && <small>{result.runtimeMs} ms</small>}
            </div>
            {result.rows && result.rows.length > 0 && (
              <div className="coding-pad__table-wrap">
                <table>
                  <thead><tr>{Object.keys(result.rows[0]).map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>{result.rows.map((row, index) => <tr key={index}>{Object.values(row).map((value, cell) => <td key={cell}>{String(value ?? "NULL")}</td>)}</tr>)}</tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <footer className="coding-pad__actions">
        <span>⌘/Ctrl + Enter to run</span>
        <div>
          <button type="button" onClick={() => void run()} disabled={!source.trim()}><Play size={15} /> Run</button>
          <button className="primary" type="button" onClick={() => void submit()} disabled={!source.trim()}><Send size={15} /> Submit</button>
        </div>
      </footer>
    </section>
  );
}
