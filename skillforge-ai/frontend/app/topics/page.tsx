import Link from "next/link";
import { ArrowRight } from "lucide-react";

const topics = [
  ["Python", "Coding patterns, collections, algorithms and data-processing exercises."],
  ["SQL", "Joins, windows, retention, aggregation, optimization and analytics patterns."],
  ["PySpark", "Transformations, shuffles, skew, partitioning, Delta and production pipelines."],
  ["Snowflake", "Architecture, warehouses, performance, security, governance and cost."],
  ["Data Engineering", "CDC, orchestration, quality, lineage, recovery and migration scenarios."],
  ["Cloud", "AWS, Azure and GCP architecture scenarios for modern data platforms."],
  ["System Design", "End-to-end platform design, scale, reliability and tradeoff reasoning."],
  ["AI Architecture", "RAG, vector search, agents, evaluation, governance and AI data systems."],
] as const;

export default function TopicsPage() {
  return <main className="min-h-screen bg-[#090b0e] px-6 py-12 text-white lg:px-10">
    <div className="mx-auto max-w-6xl">
      <Link href="/" className="text-sm text-white/45 hover:text-white">← SkillForge AI</Link>
      <p className="mt-16 text-xs uppercase tracking-[.22em] text-violet-300">Coverage map</p>
      <h1 className="mt-3 text-5xl font-semibold tracking-tight">Practice the full data engineering interview surface.</h1>
      <p className="mt-5 max-w-2xl text-lg leading-8 text-white/50">The normalized corpus spans coding, platform architecture, cloud, certification-style questions and enterprise scenarios rather than treating data engineering as SQL alone.</p>
      <div className="mt-12 grid gap-4 md:grid-cols-2">{topics.map(([name,body]) => <article key={name} className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="text-xl font-semibold">{name}</h2><p className="mt-2 text-sm leading-6 text-white/48">{body}</p></article>)}</div>
      <Link href="/signup" className="mt-10 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 font-semibold text-black">Start practicing <ArrowRight size={16}/></Link>
    </div>
  </main>;
}
