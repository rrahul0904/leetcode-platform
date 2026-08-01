"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, Clock3, Route, Target } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { getContentStats } from "@/lib/api";
import { learningPaths, titleCaseSlug } from "@/lib/product-data";

export function LearningPaths() {
  const stats = useQuery({ queryKey: ["content-stats"], queryFn: ({ signal }) => getContentStats(signal) });
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const active = learningPaths.find((path) => path.id === selectedPath);
  return (
    <div className="page-content">
      <PageHeader eyebrow="LEARNING PATHS" title="Build a deliberate preparation sequence." description="Role-aligned weekly plans blend coding, SQL, architecture, and simulation evidence without duplicating the canonical question bank." />
      {active && <EvidenceNote tone="success"><strong>{active.title} is your active local path.</strong><span>Its staged plan appears below; persistent scheduling will move to the profile service.</span></EvidenceNote>}
      <section className="path-grid section-block">
        {learningPaths.map((path) => {
          const selected = path.id === selectedPath;
          const questionCount = path.tracks.reduce((total, track) => total + (stats.data?.track_counts[track] ?? 0), 0);
          return <article className={`path-card path-card--${path.accent} ${selected ? "path-card--selected" : ""}`} key={path.id}><div className="path-card__top"><Route size={22} /><span>{path.role}</span></div><h2>{path.title}</h2><div className="path-meta"><span><Clock3 size={14} /> {path.duration}</span><span>{path.hours}</span><span>{questionCount.toLocaleString()} planned briefs</span></div><div className="path-tracks">{path.tracks.map((track, index) => <div key={track}><i>{index + 1}</i><span><strong>{titleCaseSlug(track)}</strong><small>{stats.data?.track_counts[track] ?? "—"} planned</small></span></div>)}</div><ul>{path.outcomes.map((outcome) => <li key={outcome}><Check size={14} /> {outcome}</li>)}</ul><button className={`button ${selected ? "button--dark" : "button--ghost"}`} onClick={() => setSelectedPath(selected ? null : path.id)}>{selected ? "Selected" : "Use this path"}{!selected && <ArrowRight size={15} />}</button></article>;
        })}
      </section>
      {active && <section className="panel section-block"><SectionHeading eyebrow="LOCAL STUDY PLAN" title={`${active.title}: first four weeks`} aside={<Link className="text-link" href={`/question-bank?track=${active.tracks[0]}`}>Browse first track <ArrowRight size={14} /></Link>} /><div className="week-grid">{active.tracks.map((track, index) => <div key={track}><span>WEEK {index * 2 + 1}–{index * 2 + 2}</span><strong>{titleCaseSlug(track)}</strong><p>Concept review → guided briefs → timed practice → written reflection.</p><small><Target size={13} /> Evidence target: clarity, correctness, and trade-off depth</small></div>)}</div></section>}
    </div>
  );
}
