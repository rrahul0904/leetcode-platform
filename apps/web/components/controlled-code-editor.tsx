"use client";

import { Braces, Database, Maximize2, Minimize2, RotateCcw } from "lucide-react";
import { type KeyboardEvent, useMemo, useRef, useState } from "react";

export type WorkspaceLanguage = "python" | "sql";

type ControlledCodeEditorProps = {
  language: WorkspaceLanguage;
  source: string;
  starterSource: string;
  disabled?: boolean;
  saveState: string;
  onChange: (source: string) => void;
  onRun: () => void;
  onSubmit: () => void;
};

const runtimeLabel: Record<WorkspaceLanguage, string> = {
  python: "PYTHON 3.13",
  sql: "POSTGRESQL 18",
};

export function ControlledCodeEditor({
  language,
  source,
  starterSource,
  disabled = false,
  saveState,
  onChange,
  onRun,
  onSubmit,
}: ControlledCodeEditorProps) {
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const numbers = useMemo(
    () =>
      Array.from(
        { length: Math.max(1, source.split("\n").length) },
        (_, index) => index + 1,
      ),
    [source],
  );

  function insertText(text: string) {
    const editor = editorRef.current;
    if (!editor) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    onChange(`${source.slice(0, start)}${text}${source.slice(end)}`);
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
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key === "Enter") {
      event.preventDefault();
      if (!disabled && source.trim()) onSubmit();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (!disabled && source.trim()) onRun();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      editorRef.current?.blur();
      window.requestAnimationFrame(() => editorRef.current?.focus());
    }
    if (event.key === "Escape" && fullscreen) {
      event.preventDefault();
      setFullscreen(false);
    }
  }

  return (
    <div className={`controlled-editor ${fullscreen ? "controlled-editor--fullscreen" : ""}`}>
      <header className="controlled-editor__toolbar">
        <div>
          {language === "sql" ? <Database size={15} /> : <Braces size={15} />}
          <strong>{runtimeLabel[language]}</strong>
          <span>{saveState}</span>
        </div>
        <div>
          <button
            type="button"
            aria-label="Reset to starter code"
            disabled={disabled}
            onClick={() => onChange(starterSource)}
          >
            <RotateCcw size={15} />
          </button>
          <button
            type="button"
            aria-label={fullscreen ? "Exit full screen" : "Enter full screen"}
            onClick={() => setFullscreen((value) => !value)}
          >
            {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      </header>
      <div className="controlled-editor__body">
        <pre aria-hidden="true">{numbers.join("\n")}</pre>
        <textarea
          ref={editorRef}
          aria-label={`${runtimeLabel[language]} source code`}
          disabled={disabled}
          spellCheck={false}
          value={source}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>
      <footer>
        <span>Ctrl/Cmd+Enter Run · Shift+Ctrl/Cmd+Enter Submit · Esc Fullscreen</span>
      </footer>
    </div>
  );
}
