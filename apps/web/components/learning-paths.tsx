"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  Clock3,
  Layers3,
  PlayCircle,
  Route,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { getContentStats } from "@/lib/api";
import { learningPaths, titleCaseSlug } from "@/lib/product-data";

const taskTemplates = [
  {
    eyebrow: "CONCEPT FOUNDATION",
    title: "Build the mental model",
    description: "Review the system boundary, vocabulary, invariants, and common failure modes before touching an implementation.",
    duration: "35 min",
    kind: "Reading + notes",
  },
  {
    eyebrow: "GUIDED PRACTICE",
    title: "Work a representative problem",
    description: "Solve one carefully selected brief while writing assumptions, alternatives, and verification steps.",
    duration: "50 min",
    kind: "Interactive lab",
  },
  {
    eyebrow: "TIMED EVIDENCE",
    title: "Perform under interview constraints",
    description: "Complete a focused prompt with a visible clock, explicit decision record, and post-session reflection.",
    duration: "45 min",
    kind: "Timed practice",
  },
  {
    eyebrow: "REINFORCEMENT",
    title: "Close the weakest gap",
    description: "Revisit the missed concept using spaced repetition and one narrower follow-up exercise.",
    duration: "25 min",
    kind: "Revision block",
  },
] as const;

export function LearningPaths() {
  const stats = useQuery({
    queryKey: ["content-stats"],
    queryFn: ({ signal }) => getContentStats(signal),
  });
  const [selectedPath, setSelectedPath] = useState<string>(
    learningPaths[0]?.id ?? "",
  );
  const active = learningPaths.find((path) => path.id === selectedPath) ?? learningPaths[0];
  const [selectedTrack, setSelectedTrack] = useState<string>(
    active?.tracks[0] ?? "",
  );

  const totalBriefs = useMemo(
    () =>
      active?.tracks.reduce(
        (total, track) => total + (stats.data?.track_counts[track] ?? 0),
        0,
      ) ?? 0,
    [active, stats.data?.track_counts],
  );

  if (!active) return null;

  const track = active.tracks.includes(
    selectedTrack as (typeof active.tracks)[number],
  )
    ? (selectedTrack as (typeof active.tracks)[number])
    : active.tracks[0];
  const selectedTrackIndex = Math.max(0, active.tracks.indexOf(track));
  const progress = Math.round(((selectedTrackIndex + 1) / active.tracks.length) * 100);

  function choosePath(pathId: string) {
    const next = learningPaths.find((path) => path.id === pathId);
    setSelectedPath(pathId);
    setSelectedTrack(next?.tracks[0] ?? "");
  }

  return (
    <div className="curriculum-experience">
      <aside className="curriculum-rail">
        <div className="curriculum-rail__heading">
          <span>RIGOR CURRICULUM</span>
          <strong>Your preparation map</strong>
        </div>

        <div className="curriculum-path-picker">
          <span>ACTIVE ROLE PATH</span>
          {learningPaths.map((path) => (
            <button
              className={path.id === active.id ? "is-active" : ""}
              key={path.id}
              onClick={() => choosePath(path.id)}
              type="button"
            >
              <Route size={14} />
              <span><strong>{path.title}</strong><small>{path.duration} · {path.hours}</small></span>
              <ChevronDown size={13} />
            </button>
          ))}
        </div>

        <nav aria-label="Curriculum domains" className="curriculum-domains">
          <span>DOMAIN PROGRESS</span>
          {active.tracks.map((item, index) => {
            const current = item === track;
            const completed = index < selectedTrackIndex;
            const domainProgress = completed ? 100 : current ? 35 : 0;
            return (
              <button
                aria-current={current ? "step" : undefined}
                className={current ? "is-current" : completed ? "is-complete" : ""}
                key={item}
                onClick={() => setSelectedTrack(item)}
                type="button"
              >
                <i>{completed ? <Check size={11} /> : String(index + 1).padStart(2, "0")}</i>
                <span>
                  <strong>{titleCaseSlug(item)}</strong>
                  <small>{domainProgress}% complete</small>
                  <em><b style={{ width: `${domainProgress}%` }} /></em>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="curriculum-rail__footer">
          <div><Target size={15} /><span><strong>{progress}%</strong><small>path progress</small></span></div>
          <Link href="/progress">View readiness <ArrowRight size={13} /></Link>
        </div>
      </aside>

      <main className="curriculum-main">
        <header className="curriculum-hero">
          <div>
            <span className="cert-kicker">{active.role} · {active.duration}</span>
            <h1>{active.title}</h1>
            <p>
              A deliberate sequence of concept work, guided practice, timed evidence,
              and revision. Each domain is tied to the same canonical problem bank and
              readiness model.
            </p>
          </div>
          <div className="curriculum-hero__metrics">
            <div><strong>{active.tracks.length}</strong><span>domains</span></div>
            <div><strong>{totalBriefs.toLocaleString()}</strong><span>available briefs</span></div>
            <div><strong>{active.hours}</strong><span>weekly pace</span></div>
          </div>
        </header>

        <section className="curriculum-domain-overview">
          <div className="curriculum-section-heading">
            <span>CURRICULUM DOMAINS</span>
            <h2>{active.tracks.length} domains, one coherent interview system.</h2>
            <p>Move across the path in order or open the domain that needs attention today.</p>
          </div>
          <div className="curriculum-domain-grid">
            {active.tracks.map((item, index) => {
              const current = item === track;
              const count = stats.data?.track_counts[item] ?? 0;
              return (
                <button
                  className={current ? "curriculum-domain-card is-current" : "curriculum-domain-card"}
                  key={item}
                  onClick={() => setSelectedTrack(item)}
                  type="button"
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <Layers3 size={18} />
                  <h3>{titleCaseSlug(item)}</h3>
                  <p>{count.toLocaleString()} canonical briefs connected to this domain.</p>
                  <em>{current ? "Current domain" : "Open domain"} <ArrowRight size={13} /></em>
                </button>
              );
            })}
          </div>
        </section>

        <section className="curriculum-work">
          <div className="curriculum-section-heading curriculum-section-heading--row">
            <div>
              <span>CURRENT DOMAIN</span>
              <h2>{titleCaseSlug(track)}</h2>
            </div>
            <Link href={`/question-bank?track=${track}`}>
              Browse problem bank <ArrowRight size={14} />
            </Link>
          </div>

          <div className="curriculum-task-grid">
            {taskTemplates.map((task, index) => (
              <article className={index === 1 ? "curriculum-task is-featured" : "curriculum-task"} key={task.title}>
                <span>{task.eyebrow}</span>
                <div><BookOpen size={17} /><small>{task.kind}</small></div>
                <h3>{task.title}</h3>
                <p>{task.description}</p>
                <footer>
                  <span><Clock3 size={13} /> {task.duration}</span>
                  <Link href={index === 2 ? "/mock-interviews" : `/question-bank?track=${track}`}>
                    Start <ArrowRight size={13} />
                  </Link>
                </footer>
              </article>
            ))}
          </div>
        </section>

        <section className="curriculum-guides">
          <div className="curriculum-section-heading">
            <span>GUIDED PROJECTS & TUTORIALS</span>
            <h2>Practice the full decision, not only the final answer.</h2>
          </div>
          <div className="curriculum-guide-list">
            {active.outcomes.slice(0, 3).map((outcome, index) => (
              <article key={outcome}>
                <i>{index + 1}</i>
                <div>
                  <span>{index === 0 ? "GUIDED PROJECT" : "PRACTICAL TUTORIAL"}</span>
                  <h3>{outcome}</h3>
                  <p>Work through assumptions, architecture, failure modes, and verification evidence.</p>
                </div>
                <span><PlayCircle size={15} /> {35 + index * 10} min</span>
                <ArrowRight size={16} />
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
