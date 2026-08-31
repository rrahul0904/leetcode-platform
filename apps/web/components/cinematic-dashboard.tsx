"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleGauge,
  Clock3,
  Flame,
  Route,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";

import { LoadingState } from "@/components/page-ui";
import {
  getCandidateCompetencies,
  getCandidateReadiness,
  getNextAction,
  getProfile,
  getPublishedQuestions,
  getSubmissions,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCaseSlug } from "@/lib/product-data";

function percentage(value: number | undefined) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function dateLabel(value: string | undefined) {
  if (!value) return "No activity yet";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function CinematicDashboard() {
  const { principal } = useAuth();
  const isCandidate = principal?.roles.includes("candidate") ?? false;

  const profile = useQuery({
    queryKey: ["candidate-profile"],
    queryFn: ({ signal }) => getProfile(signal),
    enabled: isCandidate,
    retry: false,
  });
  const readiness = useQuery({
    queryKey: ["candidate-readiness"],
    queryFn: ({ signal }) => getCandidateReadiness(signal),
    enabled: isCandidate,
    retry: false,
  });
  const competencies = useQuery({
    queryKey: ["candidate-competencies"],
    queryFn: ({ signal }) => getCandidateCompetencies(signal),
    enabled: isCandidate,
    retry: false,
  });
  const submissions = useQuery({
    queryKey: ["candidate-submissions"],
    queryFn: ({ signal }) => getSubmissions(signal),
    enabled: isCandidate,
    retry: false,
  });
  const nextAction = useQuery({
    queryKey: ["candidate-next-action"],
    queryFn: ({ signal }) => getNextAction(signal),
    enabled: isCandidate,
    retry: false,
  });
  const questions = useQuery({
    queryKey: ["published-questions", "overview"],
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

  if (!isCandidate) {
    return (
      <div className="cinematic-page">
        <section className="cinematic-hero">
          <div className="cinematic-hero__copy">
            <span className="cinematic-kicker">RIGOR · SKILLFORGE PLATFORM</span>
            <h1>Govern the content behind SkillForge.</h1>
            <p>
              Candidate preparation stays in SkillForge. Content governance,
              review, sources, and publication remain in the Rigor management
              workspace.
            </p>
            <div className="cinematic-actions">
              <Link
                className="cinematic-button cinematic-button--primary"
                href="/admin/questions"
              >
                Open content management <ArrowRight size={16} />
              </Link>
              <Link
                className="cinematic-button cinematic-button--quiet"
                href="/content-review"
              >
                Review queue
              </Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

  const firstName = principal?.display_name?.split(/\s+/)[0] || "Candidate";
  const recentSubmissions = submissions.data?.slice(0, 3) ?? [];
  const skillRows = [...(competencies.data ?? [])]
    .sort((left, right) => right.evidence_count - left.evidence_count || right.score - left.score)
    .slice(0, 5);
  const gaps = readiness.data?.critical_gaps.slice(0, 3) ?? [];
  const targetRole =
    profile.data?.target_roles[0] ?? readiness.data?.target_role ?? "Your target role";
  const recommendation = nextAction.data;
  const fallbackQuestion = questions.data?.items[0];
  const recommendationHref =
    recommendation?.href ??
    (fallbackQuestion ? `/question-bank/${fallbackQuestion.slug}` : "/question-bank");
  const recommendationTitle =
    recommendation?.title ?? fallbackQuestion?.title ?? "Start your first practice question";
  const overallScore = readiness.data?.overall.score;
  const overallConfidence = readiness.data?.overall.confidence;
  const evidenceCount = readiness.data?.evidence_count ?? 0;

  const initialLoading =
    profile.isLoading &&
    readiness.isLoading &&
    submissions.isLoading &&
    questions.isLoading;

  if (initialLoading) {
    return (
      <div className="cinematic-page">
        <LoadingState label="Building your SkillForge overview" />
      </div>
    );
  }

  return (
    <div className="cinematic-page">
      <section className="cinematic-hero" aria-labelledby="skillforge-overview-title">
        <div className="cinematic-hero__glow" aria-hidden="true" />
        <div className="cinematic-hero__copy">
          <span className="cinematic-kicker">SKILLFORGE · OVERVIEW</span>
          <h1 id="skillforge-overview-title">
            Welcome back, <em>{firstName}.</em>
          </h1>
          <p>
            {profile.data
              ? `You are preparing for ${targetRole}. Every completed submission strengthens the evidence behind your readiness.`
              : "Complete your profile so SkillForge can prioritize the right skills, questions, and interview sequence for you."}
          </p>
          <div className="cinematic-actions">
            <Link
              className="cinematic-button cinematic-button--primary"
              href={recommendationHref}
            >
              {evidenceCount > 0 ? "Continue practicing" : "Start practicing"}
              <ArrowRight size={16} />
            </Link>
            {!profile.data && (
              <Link
                className="cinematic-button cinematic-button--quiet"
                href="/onboarding"
              >
                Complete onboarding
              </Link>
            )}
          </div>
          <div className="cinematic-proof">
            <span className="cinematic-proof__dot" />
            <span>{targetRole}</span>
            <i />
            <span>{evidenceCount} evidence signals</span>
          </div>
        </div>

        <div className="capability-orb" aria-label="Candidate readiness summary">
          <div className="capability-orb__halo" />
          <div className="capability-orb__sphere">
            <span className="orb-grid orb-grid--one" />
            <span className="orb-grid orb-grid--two" />
            <CircleGauge className="orb-core" size={38} />
          </div>
          <div className="capability-orb__caption">
            <span>OVERALL READINESS</span>
            <strong>{overallScore === undefined ? "No evidence yet" : percentage(overallScore)}</strong>
          </div>
        </div>
      </section>

      <section className="cinematic-metrics" aria-label="Candidate readiness metrics">
        <article>
          <span>READINESS</span>
          <strong>{overallScore === undefined ? "—" : percentage(overallScore)}</strong>
          <small>evidence weighted</small>
        </article>
        <article>
          <span>CONFIDENCE</span>
          <strong>{overallConfidence === undefined ? "—" : percentage(overallConfidence)}</strong>
          <small>signal confidence</small>
        </article>
        <article>
          <span>SUBMISSIONS</span>
          <strong>{submissions.data?.length ?? 0}</strong>
          <small>durable attempts</small>
        </article>
        <article>
          <span>SKILLS</span>
          <strong>{competencies.data?.filter((item) => item.evidence_count > 0).length ?? 0}</strong>
          <small>with evidence</small>
        </article>
      </section>

      <section className="cinematic-section cinematic-section--split">
        <div className="cinematic-manifesto">
          <span className="cinematic-kicker">RECOMMENDED NEXT</span>
          <h2>{recommendationTitle}</h2>
          <p>
            {recommendation?.reasons?.[0] ??
              "SkillForge will refine this recommendation as you build submission evidence."}
          </p>
          <Link className="cinematic-text-link" href={recommendationHref}>
            Open recommendation <ArrowRight size={15} />
          </Link>
        </div>

        <div className="cinematic-recent">
          <div className="cinematic-recent__heading">
            <span>RECENT ACTIVITY</span>
            <Link href="/progress">View progress</Link>
          </div>
          {recentSubmissions.map((submission, index) => (
            <Link
              href={`/question-bank/${submission.question_slug}`}
              key={submission.id}
            >
              <span className="cinematic-recent__number">0{index + 1}</span>
              <div>
                <strong>{submission.question_title}</strong>
                <small>
                  {submission.status.toUpperCase()} · {dateLabel(submission.completed_at)}
                </small>
              </div>
              {submission.status === "passed" ? (
                <CheckCircle2 size={15} />
              ) : (
                <ArrowRight size={15} />
              )}
            </Link>
          ))}
          {recentSubmissions.length === 0 && (
            <div className="cinematic-empty">
              <Clock3 size={20} />
              <span>Your completed submissions will appear here.</span>
            </div>
          )}
        </div>
      </section>

      <section className="cinematic-section">
        <div className="cinematic-section__heading">
          <div>
            <span className="cinematic-kicker">SKILL COVERAGE</span>
            <h2>Readiness is backed by competency evidence.</h2>
          </div>
          <p>
            Scores strengthen through repeated, recent, independent evidence—not
            through demo counters or AI-generated percentages.
          </p>
        </div>

        <div className="cinematic-track-grid">
          {skillRows.map((skill) => (
            <article className="cinematic-track" key={skill.competency_id}>
              <div className="cinematic-track__top">
                <span>{skill.trend.replaceAll("_", " ").toUpperCase()}</span>
                <Target size={20} />
              </div>
              <h3>{skill.name}</h3>
              <p>
                {percentage(skill.score)} readiness · {skill.evidence_count} evidence
                {skill.evidence_count === 1 ? " signal" : " signals"}
              </p>
              <span className="cinematic-track__open">
                Confidence {percentage(skill.confidence)}
              </span>
            </article>
          ))}
          {skillRows.length === 0 && (
            <Link className="cinematic-track" href="/question-bank">
              <div className="cinematic-track__top">
                <span>NO EVIDENCE YET</span>
                <BookOpen size={20} />
              </div>
              <h3>Build your first skill signal</h3>
              <p>
                Complete a runnable question and submit it to begin building your
                competency profile.
              </p>
              <span className="cinematic-track__open">
                Open question bank <ArrowRight size={14} />
              </span>
            </Link>
          )}
        </div>
      </section>

      <section className="cinematic-section cinematic-section--split">
        <div className="cinematic-manifesto">
          <span className="cinematic-kicker">WEAK AREAS</span>
          <h2>{gaps.length ? "Focus where the evidence is weakest." : "No critical gaps yet."}</h2>
          <p>
            {gaps.length
              ? gaps
                  .map((gap) => `${gap.name} ${percentage(gap.score)}`)
                  .join(" · ")
              : "As you submit more work, SkillForge will identify the competencies that need deliberate practice."}
          </p>
          <Link className="cinematic-text-link" href="/progress">
            Inspect readiness evidence <ArrowRight size={15} />
          </Link>
        </div>

        <div className="cinematic-recent">
          <div className="cinematic-recent__heading">
            <span>AVAILABLE NOW</span>
            <Link href="/question-bank">Question Bank</Link>
          </div>
          {questions.data?.items.map((question, index) => (
            <Link href={`/question-bank/${question.slug}`} key={question.slug}>
              <span className="cinematic-recent__number">0{index + 1}</span>
              <div>
                <strong>{question.title}</strong>
                <small>
                  {titleCaseSlug(question.track)} · {question.difficulty} · {question.estimated_duration_minutes} min
                </small>
              </div>
              <ArrowRight size={15} />
            </Link>
          ))}
          {questions.data?.items.length === 0 && (
            <div className="cinematic-empty">
              <Route size={20} />
              <span>No published questions are available yet.</span>
            </div>
          )}
        </div>
      </section>

      <section className="cinematic-section">
        <div className="cinematic-track-grid">
          <Link className="cinematic-track" href="/question-bank">
            <div className="cinematic-track__top">
              <span>PRACTICE</span>
              <BookOpen size={20} />
            </div>
            <h3>Question Bank</h3>
            <p>Search governed questions by track, skill, difficulty, and completion state.</p>
            <span className="cinematic-track__open">Browse questions <ArrowRight size={14} /></span>
          </Link>
          <Link className="cinematic-track" href="/progress">
            <div className="cinematic-track__top">
              <span>EVIDENCE</span>
              <Flame size={20} />
            </div>
            <h3>Progress</h3>
            <p>Inspect readiness, competency evidence, gaps, strengths, and recent outcomes.</p>
            <span className="cinematic-track__open">View progress <ArrowRight size={14} /></span>
          </Link>
          <Link className="cinematic-track" href="/onboarding">
            <div className="cinematic-track__top">
              <span>PROFILE</span>
              <Sparkles size={20} />
            </div>
            <h3>Preparation profile</h3>
            <p>Keep target roles, companies, interview date, and priority skills current.</p>
            <span className="cinematic-track__open">Edit profile <ArrowRight size={14} /></span>
          </Link>
        </div>
      </section>
    </div>
  );
}
