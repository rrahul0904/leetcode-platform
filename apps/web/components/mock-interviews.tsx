"use client";

import { CheckCircle2, Clock3, Play, RotateCcw, ShieldAlert, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { mockFocuses } from "@/lib/product-data";

const roles = ["Senior engineer", "Staff engineer", "Principal engineer", "Engineering manager"];

export function MockInterviews() {
  const [focusId, setFocusId] = useState<string>(mockFocuses[2].id);
  const [role, setRole] = useState(roles[1]);
  const [duration, setDuration] = useState(45);
  const [started, setStarted] = useState(false);
  const [remaining, setRemaining] = useState(duration * 60);
  const focus = mockFocuses.find((item) => item.id === focusId) ?? mockFocuses[0];
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const phaseMinutes = useMemo(() => Math.floor(duration / focus.phases.length), [duration, focus.phases.length]);

  useEffect(() => {
    if (!started || remaining <= 0) return;
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [started, remaining]);

  function startSession() { setRemaining(duration * 60); setStarted(true); }
  function resetSession() { setStarted(false); setRemaining(duration * 60); }

  return (
    <div className="page-content">
      <PageHeader eyebrow="MOCK INTERVIEWS" title="Rehearse the interview as a sequence of decisions." description="Configure a timed agenda, follow explicit phases, and capture evidence. Stateful AI interviewing and transcript evaluation remain disconnected until consent and provider controls exist." />
      <EvidenceNote><strong>Deterministic session mode is available now.</strong><span>No microphone, recording, external model, or private-data transfer is active in this local build.</span></EvidenceNote>
      <section className="mock-layout section-block">
        <div className="panel mock-config">
          <SectionHeading eyebrow="SESSION BUILDER" title="Interview configuration" />
          <fieldset><legend>Focus</legend><div className="choice-grid">{mockFocuses.map((item) => <button className={item.id === focusId ? "choice choice--selected" : "choice"} key={item.id} onClick={() => { setFocusId(item.id); resetSession(); }}><Sparkles size={16} />{item.label}</button>)}</div></fieldset>
          <div className="form-grid"><label><span>Target role</span><select value={role} onChange={(event) => setRole(event.target.value)}>{roles.map((item) => <option key={item}>{item}</option>)}</select></label><label><span>Duration</span><select value={duration} onChange={(event) => { setDuration(Number(event.target.value)); setStarted(false); setRemaining(Number(event.target.value) * 60); }}><option value={30}>30 minutes</option><option value={45}>45 minutes</option><option value={60}>60 minutes</option></select></label></div>
          {!started ? <button className="button button--primary button--full" onClick={startSession}><Play size={16} /> Start local session</button> : <button className="button button--ghost button--full" onClick={resetSession}><RotateCcw size={16} /> Reset session</button>}
        </div>
        <div className={`session-board ${started ? "session-board--active" : ""}`}>
          <div className="session-board__header"><div><span>{role}</span><strong>{focus.label}</strong></div><div className="session-clock"><Clock3 size={17} /> {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}</div></div>
          <div className="phase-list">{focus.phases.map((phase, index) => <div key={phase}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{phase}</strong><small>~{phaseMinutes} minutes</small></div>{started && index === 0 && remaining > 0 ? <i>NOW</i> : <CheckCircle2 size={17} />}</div>)}</div>
          <div className="session-prompt"><ShieldAlert size={19} /><div><strong>Evidence capture</strong><p>Write assumptions, decisions, alternatives, failure modes, and verification steps. The local timer does not score or transmit your work.</p></div></div>
        </div>
      </section>
    </div>
  );
}
