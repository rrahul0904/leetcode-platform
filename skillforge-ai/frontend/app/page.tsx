import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { RotatingGlobe } from "@/components/rotating-globe";

const domains = [
  ["01", "SQL & Analytics", "Window functions, joins, performance, data quality and query design."],
  ["02", "Python & PySpark", "Coding fluency, transformation patterns, distributed execution and debugging."],
  ["03", "Modern Data Platforms", "Snowflake, Databricks, BigQuery, orchestration, governance and cost."],
  ["04", "System Design", "End-to-end data architecture, reliability, scale, tradeoffs and operational evidence."],
  ["05", "AI Data Architecture", "RAG, vector search, agents, evaluation, observability and governance."],
] as const;

const learningLayers = [
  ["Practice", "Solve coding, MCQ and enterprise scenario questions in focused workspaces."],
  ["Understand", "Use separate explanations, multiple approaches, complexity and system-design context."],
  ["Search", "Find material by keyword, meaning, topic, company-style signals and architecture intent."],
  ["Improve", "Track attempts, bookmarks and readiness while the AI tutor focuses on missing reasoning."],
] as const;

export default function HomePage() {
  return <main className="sf-public">
    <header className="sf-public-header">
      <Link href="/" className="sf-public-brand"><span className="sf-public-brandmark">S</span><span>SkillForge <em>AI</em></span></Link>
      <nav className="sf-public-nav"><Link href="/topics">Topics</Link><Link href="/learning-paths">Paths</Link><Link href="/pricing">Pricing</Link></nav>
      <div className="sf-public-account"><Link className="sf-public-login" href="/login">Sign in</Link><Link className="sf-public-small-cta" href="/signup">Start free</Link></div>
    </header>

    <section className="sf-hero-editorial">
      <div className="sf-hero-track"><span className="sf-hero-track-dot"/>Data engineering interview intelligence</div>
      <h1>Prepare for the interview <em>as a system,</em> not a list of questions.</h1>
      <p>SkillForge brings coding, data platforms, architecture, company-style signals, system design and AI-guided reasoning into one source-backed practice environment.</p>
      <div className="sf-hero-actions"><Link href="/signup" className="sf-hero-primary">Start practicing <ArrowRight size={15}/></Link><Link href="/topics" className="sf-hero-secondary">Explore the curriculum</Link></div>
      <div className="sf-hero-proof">24,800 normalized source records · 1,800 enterprise scenarios · governed provenance</div>
    </section>

    <RotatingGlobe/>

    <div className="sf-editorial-rule"/>

    <section className="sf-editorial-section">
      <div className="sf-editorial-section-intro"><div><div className="sf-editorial-kicker">The curriculum</div><h2>One preparation layer for every part of the data interview.</h2></div><p>The original source material spans coding solutions, company-wise observations, competitive-programming patterns and system-design notes. SkillForge uses those sources under explicit provenance and rights controls instead of flattening them into one anonymous question dump.</p></div>
      <div className="sf-domain-lines">{domains.map(([index,title,body]) => <Link href="/topics" className="sf-domain-line" key={title}><span className="sf-domain-index">{index}</span><strong>{title}</strong><span>{body}</span><span className="sf-domain-arrow">↗</span></Link>)}</div>
      <div className="sf-metric-strip"><div className="sf-metric"><strong>24,800</strong><span>Normalized records</span></div><div className="sf-metric"><strong>22</strong><span>Primary governed banks</span></div><div className="sf-metric"><strong>92k+</strong><span>Company observations in source inventory</span></div><div className="sf-metric"><strong>1,800</strong><span>Enterprise scenarios</span></div></div>
    </section>

    <div className="sf-editorial-rule"/>

    <section className="sf-editorial-section sf-editorial-split">
      <div className="sf-editorial-sticky"><div className="sf-editorial-kicker">How SkillForge works</div><h2>Editorial depth first. Application controls only when they help.</h2></div>
      <div className="sf-editorial-copy">{learningLayers.map(([label,title]) => <article key={label}><small>{label}</small><h3>{title.split(". ")[0]}</h3><p>{title}</p></article>)}</div>
    </section>

    <footer className="sf-public-footer"><span>SkillForge AI · Original product design for data engineering interview preparation.</span><div className="sf-public-footer-links"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/login">Sign in</Link></div></footer>
  </main>;
}
