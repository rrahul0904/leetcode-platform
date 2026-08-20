import Link from "next/link";
import { ArrowRight, BrainCircuit, Code2, Database, Search, ShieldCheck, Sparkles } from "lucide-react";

const capabilities = [
  [Code2, "Coding studios", "Monaco-powered Python and SQL workspaces backed by the SkillForge runner contract."],
  [Database, "Data engineering depth", "SQL, PySpark, Snowflake, cloud, pipelines, system design and enterprise scenarios."],
  [Search, "Hybrid retrieval", "Full-text plus pgvector semantic retrieval with a keyword fallback when embeddings are unavailable."],
  [BrainCircuit, "AI interview tutor", "Hints, explanations, answer review and architecture tradeoff coaching through configurable AI providers."],
  [ShieldCheck, "Governed content", "Supabase RLS, reviewer roles, source provenance, import validation and private content storage."],
  [Sparkles, "Adaptive preparation", "Progress, bookmarks and role-aligned learning paths designed around interview readiness."],
] as const;

export default function HomePage() {
  return <main className="min-h-screen bg-[#090b0e] text-white">
    <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">
      <Link href="/" className="flex items-center gap-3 font-semibold"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-black">S</span><span>SkillForge <span className="text-violet-300">AI</span></span></Link>
      <nav className="hidden items-center gap-7 text-sm text-white/60 md:flex"><Link className="hover:text-white" href="/topics">Topics</Link><Link className="hover:text-white" href="/pricing">Pricing</Link><Link className="hover:text-white" href="/login">Sign in</Link></nav>
      <Link href="/signup" className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black hover:bg-violet-100">Start practicing</Link>
    </header>

    <section className="mx-auto grid max-w-7xl gap-12 px-6 pb-20 pt-20 lg:grid-cols-[1.2fr_.8fr] lg:px-10 lg:pt-28">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-400/10 px-3 py-1.5 text-xs font-medium text-violet-200"><Sparkles size={14}/>Built for data engineering interviews</div>
        <h1 className="mt-7 max-w-4xl text-5xl font-semibold tracking-[-0.04em] sm:text-6xl lg:text-7xl">LeetCode-style practice for the <span className="text-white/50">entire data engineering interview.</span></h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-white/55">Practice coding, architecture, cloud, Snowflake, SQL, PySpark and realistic enterprise scenarios in one source-backed workspace—with semantic search and an AI tutor layered on top.</p>
        <div className="mt-9 flex flex-wrap gap-3"><Link href="/signup" className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 font-semibold text-black hover:bg-violet-100">Create free account <ArrowRight size={16}/></Link><Link href="/topics" className="rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 font-medium text-white/80 hover:bg-white/[0.08]">Explore topics</Link></div>
        <div className="mt-10 flex flex-wrap gap-x-7 gap-y-3 text-sm text-white/40"><span>24,800 normalized source records</span><span>1,800 enterprise scenarios</span><span>Python + SQL execution</span></div>
      </div>

      <div className="rounded-[2rem] border border-white/10 bg-white/[0.035] p-5 shadow-2xl shadow-violet-950/20">
        <div className="rounded-2xl border border-white/10 bg-black/40 p-5">
          <div className="flex items-center justify-between text-xs text-white/40"><span>Interview readiness</span><span>Senior Data Engineer</span></div>
          <div className="mt-5 text-5xl font-semibold">72<span className="text-xl text-white/35">/100</span></div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full w-[72%] rounded-full bg-violet-300"/></div>
          <div className="mt-7 grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-white/[0.045] p-4"><span className="text-white/40">SQL</span><strong className="mt-2 block text-xl">84%</strong></div><div className="rounded-xl bg-white/[0.045] p-4"><span className="text-white/40">Python</span><strong className="mt-2 block text-xl">77%</strong></div><div className="rounded-xl bg-white/[0.045] p-4"><span className="text-white/40">Snowflake</span><strong className="mt-2 block text-xl">69%</strong></div><div className="rounded-xl bg-white/[0.045] p-4"><span className="text-white/40">System design</span><strong className="mt-2 block text-xl">58%</strong></div></div>
        </div>
        <div className="mt-4 rounded-2xl border border-violet-400/15 bg-violet-400/[0.08] p-5"><p className="text-xs uppercase tracking-[.2em] text-violet-300">AI study coach</p><p className="mt-3 text-sm leading-6 text-white/65">Your next useful session should combine one SQL window problem with a Snowflake workload-isolation scenario.</p></div>
      </div>
    </section>

    <section className="border-t border-white/10 bg-white/[0.018]"><div className="mx-auto max-w-7xl px-6 py-20 lg:px-10"><p className="text-xs uppercase tracking-[.22em] text-white/35">One interview workstation</p><h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">Not another question list. A practice operating system.</h2><div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{capabilities.map(([Icon,title,body]) => <article key={title} className="rounded-2xl border border-white/10 bg-black/20 p-6"><Icon className="text-violet-300" size={21}/><h3 className="mt-5 text-lg font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-white/48">{body}</p></article>)}</div></div></section>

    <footer className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-10 text-sm text-white/35 sm:flex-row sm:items-center sm:justify-between lg:px-10"><span>SkillForge AI · Data engineering interview preparation</span><div className="flex gap-5"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/login">Sign in</Link></div></footer>
  </main>;
}
