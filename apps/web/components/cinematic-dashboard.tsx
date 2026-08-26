"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Braces,
  Database,
  Route,
  Sparkles,
  SquareTerminal,
} from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { ErrorState, LoadingState } from "@/components/page-ui";
import { getPracticeSummary, getProfile, getPublishedQuestions } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCaseSlug } from "@/lib/product-data";

const tracks = [
  {
    title: "Coding systems",
    description:
      "Python problem solving with isolated execution, deterministic tests, and durable progress.",
    href: "/question-bank?track=python",
    icon: Braces,
    signal: "PYTHON",
  },
  {
    title: "Data reasoning",
    description:
      "SQL, modeling, warehousing, and data architecture practice in production-like environments.",
    href: "/question-bank?track=sql",
    icon: Database,
    signal: "DATA",
  },
  {
    title: "Architecture",
    description:
      "System design and AI architecture prompts for senior, staff, and principal interviews.",
    href: "/learning-paths",
    icon: Route,
    signal: "SYSTEMS",
  },
  {
    title: "Interview simulation",
    description:
      "Timed practice, structured rubrics, and readiness evidence across complete interview loops.",
    href: "/mock-interviews",
    icon: Sparkles,
    signal: "SIMULATION",
  },
] as const;

export function CinematicDashboard() {
  const { principal } = useAuth();
  const isCandidate = principal?.roles.includes("candidate") ?? false;
  const stats = useQuery({
    queryKey: ["practice-summary"],
    queryFn: ({ signal }) => getPracticeSummary(signal),
  });
  const profile = useQuery({
    queryKey: ["candidate-profile"],
    queryFn: ({ signal }) => getProfile(signal),
    enabled: isCandidate,
  });
  const questions = useQuery({
    queryKey: ["published-questions", "cinematic-dashboard"],
    queryFn: ({ signal }) =>
      getPublishedQuestions(
        {
          query: "",
          track: "",
          skill: "",
          difficulty: "",
          role: "",
          companyStyle: "",
          completionStatus: "",
          sort: "newest",
          pageSize: 3,
        },
        signal,
      ),
  });

  return (
    <div className="cinematic-page">
      <section className="cinematic-hero" aria-labelledby="skillforge-hero-title">
        <div className="cinematic-hero__glow" aria-hidden="true" />
        <div className="cinematic-hero__copy">
          <span className="cinematic-kicker">SKILLFORGE AI · TECHNICAL INTERVIEW PLATFORM</span>
          <h1 id="skillforge-hero-title">
            Forge the skills that <em>get you hired.</em>
          </h1>
          <p>
            Train for elite data engineering, software engineering, system design,
            and AI interviews with real coding practice, governed solutions, and
            evidence-backed readiness.
          </p>
          <div className="cinematic-actions">
            <Link
              className="cinematic-button cinematic-button--primary"
              href="/question-bank"
            >
              Enter the question bank <ArrowRight size={16} />
            </Link>
            <Link
              className="cinematic-button cinematic-button--quiet"
              href="/learning-paths"
            >
              Explore preparation paths
            </Link>
          </div>
          <div className="cinematic-proof">
            <span className="cinematic-proof__dot" />
            <span>Asynchronous Python and SQL execution</span>
            <i />
            <span>Evidence-gated readiness</span>
          </div>
        </div>

        <div className="capability-orb" aria-label="SkillForge AI capability map">
          <div className="capability-orb__halo" />
          <div className="capability-orb__sphere">
            <span className="orb-grid orb-grid--one" />
            <span className="orb-grid orb-grid--two" />
            <span className="orb-node orb-node--python">PY</span>
            <span className="orb-node orb-node--sql">SQL</span>
            <span className="orb-node orb-node--system">SYS</span>
            <span className="orb-node orb-node--ai">AI</span>
            <SquareTerminal className="orb-core" size={34} />
          </div>
          <div className="capability-orb__caption">
            <span>ACTIVE PREPARATION GRAPH</span>
            <strong>
              {profile.data?.target_roles[0] ?? "Senior engineering"}
            </strong>
          </div>
        </div>
      </section>

      {stats.isError && <ErrorState retry={() => void stats.refetch()} />}
      {!stats.data && !stats.isError && (
        <LoadingState label="Reading preparation evidence" />
      )}

      {stats.data && (
        <section className="cinematic-metrics" aria-label="Platform evidence">
          <article>
            <span>PUBLISHED</span>
            <strong>
              {stats.data.published_hosted_questions.toLocaleString()}
            </strong>
            <small>hosted questions</small>
          </article>
          <article>
            <span>REFERENCES</span>
            <strong>{stats.data.external_references.toLocaleString()}</strong>
            <small>source-backed links</small>
          </article>
          <article>
            <span>SOURCES</span>
            <strong>{stats.data.approved_sources.toLocaleString()}</strong>
            <small>approved collections</small>
          </article>
          <article>
            <span>REVIEW</span>
            <strong>{stats.data.awaiting_review.toLocaleString()}</strong>
            <small>awaiting evidence</small>
          </article>
        </section>
      )}

      <section className="cinematic-section">
        <div className="cinematic-section__heading">
          <div>
            <span className="cinematic-kicker">CURRICULUM & PRACTICE</span>
            <h2>Train across the complete interview loop.</h2>
          </div>
          <p>
            Each surface shares one visual language and one durable progress
            model.
          </p>
        </div>
        <div className="cinematic-track-grid">
          {tracks.map(
            ({ title, description, href, icon: Icon, signal }, index) => (
              <Link
                className="cinematic-track"
                href={href}
                key={href}
                style={{ "--track-index": index } as CSSProperties}
              >
                <div className="cinematic-track__top">
                  <span>{signal}</span>
                  <Icon size={20} />
                </div>
                <h3>{title}</h3>
                <p>{description}</p>
                <span className="cinematic-track__open">
                  Open track <ArrowRight size={14} />
                </span>
              </Link>
            ),
          )}
        </div>
      </section>

      <section className="cinematic-section cinematic-section--split">
        <div className="cinematic-manifesto">
          <span className="cinematic-kicker">YOUR NEXT SESSION</span>
          <h2>Continue with context, not from scratch.</h2>
          <p>
            Drafts, active executions, elapsed time, and evaluation evidence
            survive navigation and reconnects.
          </p>
          <Link className="cinematic-text-link" href="/question-bank">
            Choose a problem <ArrowRight size={15} />
          </Link>
        </div>
        <div className="cinematic-recent">
          <div className="cinematic-recent__heading">
            <span>RECENTLY PUBLISHED</span>
            <Link href="/question-bank">View all</Link>
          </div>
          {questions.data?.items.map((question, index) => (
            <Link
              href={`/question-bank/${question.slug}`}
              key={question.slug}
            >
              <span className="cinematic-recent__number">0{index + 1}</span>
              <div>
                <strong>{question.title}</strong>
                <small>
                  {titleCaseSlug(question.track)} · {question.difficulty} ·{" "}
                  {question.estimated_duration_minutes} min
                </small>
              </div>
              <ArrowRight size={15} />
            </Link>
          ))}
          {questions.data?.items.length === 0 && (
            <div className="cinematic-empty">
              <BookOpen size={20} />
              <span>No published questions yet.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
