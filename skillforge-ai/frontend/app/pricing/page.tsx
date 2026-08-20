import Link from "next/link";

const plans = [
  ["Free", "$0", "Core question browser, coding studios and basic progress tracking."],
  ["Pro", "$19", "AI tutor, semantic search, learning paths, deeper analytics and review workflows."],
  ["Enterprise", "Custom", "Private content, reviewer roles, governed imports, SSO and enterprise administration."],
] as const;

export default function PricingPage() {
  return <main className="min-h-screen bg-[#090b0e] px-6 py-12 text-white lg:px-10"><div className="mx-auto max-w-6xl"><Link href="/" className="text-sm text-white/45 hover:text-white">← SkillForge AI</Link><p className="mt-16 text-xs uppercase tracking-[.22em] text-violet-300">Plans</p><h1 className="mt-3 text-5xl font-semibold tracking-tight">Start free. Upgrade when the intelligence layer matters.</h1><p className="mt-5 max-w-2xl text-lg leading-8 text-white/50">Pricing shown here is product positioning for the current build and is not yet connected to billing.</p><div className="mt-12 grid gap-4 lg:grid-cols-3">{plans.map(([name,price,body]) => <article key={name} className="rounded-2xl border border-white/10 bg-white/[0.03] p-7"><span className="text-sm text-white/45">{name}</span><div className="mt-4 text-4xl font-semibold">{price}{price.startsWith("$") && price !== "$0" ? <span className="text-base font-normal text-white/35">/month</span> : null}</div><p className="mt-5 min-h-20 text-sm leading-6 text-white/48">{body}</p><Link href="/signup" className="mt-7 block rounded-xl bg-white px-4 py-3 text-center font-semibold text-black">{name === "Enterprise" ? "Create account" : "Get started"}</Link></article>)}</div></div></main>;
}
