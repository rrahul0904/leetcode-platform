"use client";

import Editor from "@monaco-editor/react";

export function MonacoCodeEditor({ language, value, onChange }: { language: "python" | "sql"; value: string; onChange: (value: string) => void }) {
  return <div className="sf-monaco-wrap">
    <Editor
      height="100%"
      language={language === "sql" ? "sql" : "python"}
      value={value}
      onChange={(next) => onChange(next ?? "")}
      theme="vs-dark"
      loading={<div className="sf-editor-loading">Loading editor…</div>}
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        fontFamily: "JetBrains Mono, Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace",
        lineHeight: 22,
        padding: { top: 14, bottom: 14 },
        automaticLayout: true,
        scrollBeyondLastLine: false,
        wordWrap: "on",
        smoothScrolling: true,
        cursorSmoothCaretAnimation: "on",
        renderLineHighlight: "line",
        bracketPairColorization: { enabled: true },
      }}
    />
    <div className="sf-editor-status"><span>UTF-8 · Spaces: 2</span><span>{language === "sql" ? "PostgreSQL" : "Python 3.13"} · SkillForge Runner</span></div>
  </div>;
}
