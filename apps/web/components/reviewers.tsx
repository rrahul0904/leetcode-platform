"use client";

import { AlertTriangle, Plus, ShieldCheck, UserCheck, Users } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { reviewPackage } from "@/lib/product-data";

type Reviewer = { id: number; name: string; specialty: string };

export function Reviewers() {
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("Python engineering");
  const [technical, setTechnical] = useState("");
  const [editorial, setEditorial] = useState("");
  const conflict = technical !== "" && technical === editorial;
  const ready = technical !== "" && editorial !== "" && !conflict;
  const assignments = useMemo(() => ({ technical: reviewers.find((item) => String(item.id) === technical), editorial: reviewers.find((item) => String(item.id) === editorial) }), [reviewers, technical, editorial]);

  function addReviewer(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setReviewers((items) => [...items, { id: Math.max(0, ...items.map((item) => item.id)) + 1, name: trimmed, specialty }]);
    setName("");
  }

  return (
    <div className="page-content">
      <PageHeader eyebrow="REVIEWER OPERATIONS" title="Protect independence before assigning authority." description="Create a local roster and test the technical/editorial separation rule. This planning board does not grant roles or write approvals to the database." />
      <EvidenceNote tone="warning"><strong>Identity-backed RBAC is not connected.</strong><span>Roster and assignment changes are session-only planning data; durable authority requires Cognito identity, audit logs, and database policy.</span></EvidenceNote>
      <section className="reviewer-layout section-block">
        <div className="panel"><SectionHeading eyebrow="LOCAL ROSTER" title="Add a reviewer" /><form className="reviewer-form" onSubmit={addReviewer}><label><span>Display name</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Reviewer name" /></label><label><span>Specialty</span><select value={specialty} onChange={(event) => setSpecialty(event.target.value)}><option>Python engineering</option><option>Distributed systems</option><option>AI architecture</option><option>Editorial quality</option><option>Accessibility</option></select></label><button className="button button--primary" type="submit"><Plus size={15} /> Add to local roster</button></form><div className="roster-list">{reviewers.length === 0 ? <div className="mini-empty"><Users size={22} /><strong>No reviewers configured.</strong><p>Add two different people to prepare an independent assignment.</p></div> : reviewers.map((reviewer) => <div key={reviewer.id}><span>{reviewer.name.slice(0, 2).toUpperCase()}</span><div><strong>{reviewer.name}</strong><small>{reviewer.specialty}</small></div></div>)}</div></div>
        <div className="panel panel--wide"><SectionHeading eyebrow={`${reviewPackage.id} · ${reviewPackage.state}`} title="Assignment check" /><div className="assignment-card"><div><UserCheck size={19} /><label><span>Technical reviewer</span><select value={technical} onChange={(event) => setTechnical(event.target.value)}><option value="">Unassigned</option>{reviewers.map((reviewer) => <option value={reviewer.id} key={reviewer.id}>{reviewer.name} · {reviewer.specialty}</option>)}</select></label></div><div><ShieldCheck size={19} /><label><span>Editorial reviewer</span><select value={editorial} onChange={(event) => setEditorial(event.target.value)}><option value="">Unassigned</option>{reviewers.map((reviewer) => <option value={reviewer.id} key={reviewer.id}>{reviewer.name} · {reviewer.specialty}</option>)}</select></label></div></div>{conflict && <div className="inline-alert"><AlertTriangle size={17} /><span><strong>Independence violation.</strong> Technical and editorial approval must come from different reviewers.</span></div>}{ready && <div className="assignment-ready"><ShieldCheck size={20} /><div><strong>Assignment is structurally valid.</strong><p>{assignments.technical?.name} can perform technical review; {assignments.editorial?.name} can independently perform editorial review after technical approval.</p></div></div>}<div className="policy-list"><div><span>01</span><p>Authors cannot approve their own content version.</p></div><div><span>02</span><p>Technical and editorial reviewers must be different identities.</p></div><div><span>03</span><p>Every decision records evidence, outcome, identity, and timestamp.</p></div><div><span>04</span><p>Only an approved immutable version can enter publication.</p></div></div></div>
      </section>
    </div>
  );
}
