"use client";

import { useEffect, useState, type ReactNode } from "react";
import { BarChart3, Bookmark, BrainCircuit, ChevronsLeft, Code2, Database, FlaskConical, Home, Layers3, Menu, Search, ShieldCheck, Sparkles, Trophy, X } from "lucide-react";
import { StatusBadge } from "./primitives";

export type View = "dashboard"|"questions"|"python"|"sql"|"quiz"|"scenarios"|"search"|"progress"|"admin"|"bookmarks"|"paths";
type VisualTheme = "obsidian" | "navy" | "carbon";

const groups = [
  { label: "Learn", items: [["dashboard","Command Center",Home],["questions","Question Bank",Layers3],["paths","Learning Paths",Trophy],["bookmarks","Bookmarks",Bookmark]] },
  { label: "Practice", items: [["python","Python Studio",Code2],["sql","SQL Studio",Database],["quiz","MCQ Arena",FlaskConical],["scenarios","DE Scenarios",BrainCircuit]] },
  { label: "Intelligence", items: [["search","Semantic Search",Search],["progress","Progress",BarChart3]] },
  { label: "Operate", items: [["admin","Content Operations",ShieldCheck]] },
] as const;

const themeLabels: { id: VisualTheme; label: string }[] = [
  { id: "obsidian", label: "Obsidian" },
  { id: "navy", label: "Navy" },
  { id: "carbon", label: "Carbon" },
];

export function AppShell({ view, setView, children }: { view: View; setView: (view: View) => void; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [visualTheme, setVisualTheme] = useState<VisualTheme>(() => {
    if (typeof window === "undefined") return "obsidian";
    const saved = window.localStorage.getItem("skillforge-visual-theme");
    return saved === "navy" || saved === "carbon" || saved === "obsidian" ? saved : "obsidian";
  });

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); }
      if (event.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("skillforge-visual-theme", visualTheme);
  }, [visualTheme]);

  const navigate = (next: View) => { setView(next); setMobileOpen(false); setCommandOpen(false); };

  return <div className="sf-app" data-sf-theme={visualTheme}>
    <aside className={collapsed ? "sf-sidebar collapsed" : "sf-sidebar"}>
      <button className="sf-brand" onClick={() => navigate("dashboard")}><span className="sf-brand-mark">S</span><span className="sf-brand-copy"><b>SkillForge <em>AI</em></b><small>Interview Workstation</small></span></button>
      <nav>{groups.map(group => <div key={group.label} className="sf-nav-group"><div className="sf-nav-label">{group.label}</div>{group.items.map(([id,label,Icon]) => <button key={id} className={view === id ? "sf-nav-item active" : "sf-nav-item"} onClick={() => navigate(id)}><Icon size={17}/><span>{label}</span></button>)}</div>)}</nav>
      <div className="sf-side-status"><div><span>Corpus</span><StatusBadge status="ready"/></div><div><span>Intelligence</span><StatusBadge status="ai"/></div><small>24,800 indexed · demo environment</small></div>
      <button className="sf-collapse" onClick={() => setCollapsed(v => !v)}><ChevronsLeft size={16}/><span>Collapse</span></button>
    </aside>

    {mobileOpen && <div className="sf-mobile-drawer"><div className="sf-mobile-drawer-head"><span>SkillForge AI</span><button onClick={() => setMobileOpen(false)}><X/></button></div>{groups.flatMap(group => group.items).map(([id,label,Icon]) => <button key={id} onClick={() => navigate(id)}><Icon size={17}/>{label}</button>)}</div>}

    <div className="sf-main">
      <header className="sf-topbar">
        <button className="sf-mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={18}/></button>
        <button className="sf-command-trigger" onClick={() => setCommandOpen(true)}><Search size={16}/><span>Search questions, topics, commands…</span><kbd>⌘K</kbd></button>
        <div className="sf-topbar-right">
          <span className="sf-sync"><span/>Vector index ready</span>
          <div className="sf-theme-switcher" aria-label="Visual theme selector">{themeLabels.map(theme => <button key={theme.id} className={visualTheme === theme.id ? "sf-theme-chip active" : "sf-theme-chip"} onClick={() => setVisualTheme(theme.id)}>{theme.label}</button>)}</div>
          <button className="sf-avatar">RS</button>
        </div>
      </header>
      <main className="sf-content">{children}</main>
    </div>

    <div className="sf-mobile-nav">{[["dashboard",Home],["questions",Layers3],["python",Code2],["search",Sparkles],["progress",BarChart3]].map(([id,Icon]) => { const I = Icon as typeof Home; return <button key={id as string} className={view === id ? "active" : ""} onClick={() => navigate(id as View)}><I size={17}/><span>{id as string}</span></button>; })}</div>

    {commandOpen && <div className="sf-command-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setCommandOpen(false); }}><div className="sf-command"><div className="sf-command-input"><Search size={17}/><input autoFocus placeholder="Search SkillForge or type a command…"/></div>{[["questions","Open Question Bank",Layers3],["sql","Start SQL Practice",Database],["search","Semantic Search",Sparkles],["admin","Open Content Operations",ShieldCheck]].map(([id,label,Icon]) => { const I = Icon as typeof Home; return <button key={id as string} onClick={() => navigate(id as View)}><I size={17}/><span>{label as string}</span></button>; })}</div></div>}
  </div>;
}
