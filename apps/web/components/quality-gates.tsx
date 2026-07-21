"use client";

import { AlertTriangle, CheckCircle2, CircleDashed, Filter } from "lucide-react";
import { useState } from "react";

import { EvidenceNote, PageHeader } from "@/components/page-ui";
import { qualityGates } from "@/lib/product-data";

type GateState = "all" | "pass" | "attention" | "waiting";

export function QualityGates() {
  const [filter, setFilter] = useState<GateState>("all");
  const gates = qualityGates.filter(([, state]) => filter === "all" || state === filter);
  return (
    <div className="page-content">
      <PageHeader eyebrow="QUALITY GATES" title="Every publication claim needs a receipt." description="The gate board maps deterministic checks, human approvals, and immutable publication evidence for the first authored package." />
      <EvidenceNote><strong>Gate status is derived from repository artifacts.</strong><span>Waiting does not mean failure; it means the prerequisite evidence does not exist yet.</span></EvidenceNote>
      <section className="gate-summary section-block"><div><CheckCircle2 size={20} /><span><strong>4</strong><small>passed</small></span></div><div><AlertTriangle size={20} /><span><strong>1</strong><small>attention</small></span></div><div><CircleDashed size={20} /><span><strong>7</strong><small>waiting</small></span></div><div className="gate-filter"><Filter size={16} /><label><span className="sr-only">Filter gates</span><select value={filter} onChange={(event) => setFilter(event.target.value as GateState)}><option value="all">All gates</option><option value="pass">Passed</option><option value="attention">Attention</option><option value="waiting">Waiting</option></select></label></div></section>
      <section className="gate-list">{gates.map(([name, state, description]) => <article key={name} className={`gate-row gate-row--${state}`}><span className="gate-number">{String(qualityGates.findIndex(([candidate]) => candidate === name) + 1).padStart(2, "0")}</span>{state === "pass" ? <CheckCircle2 size={20} /> : state === "attention" ? <AlertTriangle size={20} /> : <CircleDashed size={20} />}<div><strong>{name}</strong><p>{description}</p></div><span className={`status-chip status-chip--${state}`}>{state}</span></article>)}</section>
    </div>
  );
}
