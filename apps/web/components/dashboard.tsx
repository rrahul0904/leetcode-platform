"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  CircleGauge,
  FileCheck2,
  ShieldCheck,
  Target,
} from "lucide-react";
import Link from "next/link";

import { ErrorState, LoadingState, SectionHeading } from "@/components/page-ui";
import {
  ApiError,
  getCandidateCompetencies,
  getCandidateReadiness,
  getNextAction,
  getProfile,
  getPublishedQuestions,
  getSubmissions,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCaseSlug } from "@/lib/product-data";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function CandidateOverview() {
  const { principal } = useAuth();
  const profile = useQuery({
    queryKey: ["candidate-profile"],
    queryFn: ({ signal }) => getProfile(signal),
    retry: false,
  });
  const readiness = useQuery({
    queryKey: ["candidate-readiness"],
    queryFn: ({ signal }) => getCandidateReadiness(signal),
    retry: false,
  });
  const competencies = useQuery({
    queryKey: ["candidate-competencies"],
    queryFn: ({ signal }) => getCandidateCompetencies(signal),
    retry: false,
  });
  const submissions = useQuery({
    queryKey: ["submissions"],
    queryFn: ({ signal }) => getSubmissions(signal),
    retry: false,
  });
  const nextAction = useQuery({
    queryKey: ["next-action"],
    queryFn: ({ signal }) => getNextAction(signal),
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
          pageSize: 4,
        },
        signal,
      ),
  });

  const profileMissing =
    profile.isError && profile.error instanceof ApiError && profile.error.status === 404;
  const hasEvidence = (readiness.data?.evidence_count ?? 0) > 0;
  const recentSubmissions = submissions.data?.slice(0, 4) ?? [];
  const skillEvidence = competencies.data?.filter((item) => item.evidence_count > 0) ?? [];
  const firstName = principal?.display_name?.split(/\s+/)[0] || "Candidate";

  if (profile.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Loading your SkillsForge AI profile" />
      </div>
    );
  }

  if (profile.isError && !profileMissing) {
    return (
      <div className="page-content">
        <ErrorState retry={() => void profile.refetch()} />
      </div>
    );
  }

  if (profileMissing) {
    return (
      <div className="page-content">
        <section className="hero hero--dashboard">
          <div>
            <span className="eyebrow">WELCOME TO SKILLSFORGE AI</span>
            <h1>Build your preparation plan before we score readiness.</h1>
            <p>
              Choose your target role, interview timeline, study capacity, and preferred
              practice language. SkillsForge AI will not invent progress before you have
              real submission evidence.
            </p>
            <div className="hero-actions">
              <Link className="button button--primary" href="/onboarding">
                Complete onboarding <ArrowRight size={16} />
              </Link>
              <Link className="button button--ghost" href="/question-bank">
                Preview question bank
              </Link>
            </div>
          </div>
          <div className="release-gate">
            <span>READINESS</span>
            <strong>—</strong>
            <p>No readiness score exists until deterministic practice evidence exists.</p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page-content">
      <section className="hero hero--dashboard">
        <div>
          <span className="eyebrow">OVERVIEW</span>
          <h1>Welcome back, {firstName}.</h1>
          <p>
            {profile.data?.target_roles.length
              ? `Preparing for ${profile.data.target_roles.join(", ")}.`
              : "Your preparation plan is ready for a target role."}{" "}
            Progress below is based on persisted submission evidence, not activity theater.
          </p>
          <div className="hero-actions">
            {nextAction.data ? (
              <Link className="button button--primary" href={nextAction.data.href}>
                Continue practicing <ArrowRight size={16} />
              </Link>
            ) : (
              <Link className="button button--primary" href="/question-bank">
                Choose a question <ArrowRight size={16} />
              </Link>
            )}
            <Link className="button button--ghost" href="/progress">
              View progress
            </Link>
          </div>
        </div>
        <div className="release-gate">
          <span>OVERALL READINESS</span>
          <strong>{hasEvidence ? percent(readiness.data!.overall.score) : "—"}</strong>
          <div className="progress-track">
            <i
              style={{
                width: hasEvidence ? percent(readiness.data!.overall.score) : "0%",
              }}
            />
          </div>
          <p>
            {hasEvidence
              ? `${readiness.data!.evidence_count} evidence records · ${percent(readiness.data!.overall.confidence)} confidence`
              : "No evidence yet. Complete a deterministic submission to establish readiness."}
          </p>
        </div>
      </section>

      <section className="status-strip" aria-label="Candidate evidence summary">
        <div className="stat stat--accent">
          <span>Submissions</span>
          <strong>{submissions.data?.length ?? 0}</strong>
          <small>durable evaluated attempts</small>
        </div>
        <div className="stat">
          <span>Skills with evidence</span>
          <strong>{skillEvidence.length}</strong>
          <small>measured competencies</small>
        </div>
        <div className="stat">
          <span>Confidence</span>
          <strong>{hasEvidence ? percent(readiness.data!.overall.confidence) : "—"}</strong>
          <small>evidence confidence</small>
        </div>
        <div className="stat">
          <span>Study capacity</span>
          <strong>{profile.data?.weekly_study_hours ?? 0}h</strong>
          <small>per week</small>
        </div>
      </section>

      <section className="dashboard-grid section-block">
        <div className="panel panel--wide">
          <SectionHeading eyebrow="RECOMMENDED NEXT" title="What to practice next" />
          {nextAction.isLoading && <LoadingState label="Ranking your next action" />}
          {nextAction.data ? (
            <div className="assignment-ready">
              <Target size={20} />
              <div>
                <strong>{nextAction.data.title}</strong>
                <p>
                  {nextAction.data.reasons.length
                    ? nextAction.data.reasons.join(" · ")
                    : "Recommended from your current evidence and target role."}
                </p>
              </div>
              <Link className="button button--primary" href={nextAction.data.href}>
                Open next <ArrowRight size={15} />
              </Link>
            </div>
          ) : (
            !nextAction.isLoading && (
              <div className="assignment-ready">
                <BookOpen size={20} />
                <div>
                  <strong>Choose your first evidence-producing question</strong>
                  <p>
                    Recommendations become more specific after SkillsForge AI has real
                    evaluation evidence.
                  </p>
                </div>
                <Link className="button button--ghost" href="/question-bank">
                  Open question bank
                </Link>
              </div>
            )
          )}
        </div>

        <div className="panel">
          <SectionHeading eyebrow="TARGET" title="Interview plan" />
          <dl className="metadata-list">
            <div>
              <dt>Role</dt>
              <dd>{profile.data?.target_roles[0] ?? "Not selected"}</dd>
            </div>
            <div>
              <dt>Interview date</dt>
              <dd>{profile.data?.interview_date ?? "Not provided"}</dd>
            </div>
            <div>
              <dt>Intensity</dt>
              <dd>{titleCaseSlug(profile.data?.preparation_intensity ?? "focused")}</dd>
            </div>
          </dl>
          <Link className="text-link" href="/profile">
            Edit profile <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="dashboard-grid section-block">
        <div className="panel panel--wide">
          <SectionHeading eyebrow="RECENT ACTIVITY" title="Evaluated submissions" />
          {submissions.isLoading && <LoadingState label="Loading submissions" />}
          {recentSubmissions.length === 0 && !submissions.isLoading ? (
            <p>
              No evaluated submissions yet. Runs are iteration; submissions create durable
              readiness evidence.
            </p>
          ) : (
            <div className="compact-list">
              {recentSubmissions.map((submission) => (
                <Link href={`/question-bank/${submission.question_slug}`} key={submission.id}>
                  <span className="question-id">
                    {Math.round(submission.evaluation.overall_score * 100)}%
                  </span>
                  <strong>{submission.question_title}</strong>
                  <small>
                    {submission.status} · {submission.runtime} ·{" "}
                    {new Date(submission.completed_at).toLocaleDateString()}
                  </small>
                  <ArrowRight size={15} />
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <SectionHeading eyebrow="SKILL COVERAGE" title="Evidence-backed skills" />
          {skillEvidence.length === 0 ? (
            <p>No competency evidence has been recorded yet.</p>
          ) : (
            <div className="evidence-list">
              {skillEvidence.slice(0, 5).map((skill) => (
                <div key={skill.competency_id}>
                  <CircleGauge size={17} />
                  <span>
                    <strong>{skill.name}</strong>
                    <small>
                      {percent(skill.score)} · {skill.evidence_count} evidence records ·{" "}
                      {skill.trend.replaceAll("_", " ")}
                    </small>
                  </span>
                </div>
              ))}
            </div>
          )}
          <Link className="text-link" href="/progress">
            Inspect all progress <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      {hasEvidence && readiness.data && (
        <section className="dashboard-grid section-block">
          <div className="panel">
            <SectionHeading eyebrow="STRONGEST AREAS" title="Current strengths" />
            {readiness.data.strongest_areas.length ? (
              <div className="evidence-list">
                {readiness.data.strongest_areas.slice(0, 4).map((skill) => (
                  <div key={skill.competency_id}>
                    <ShieldCheck size={17} />
                    <span>
                      <strong>{skill.name}</strong>
                      <small>{percent(skill.score)} readiness</small>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p>More evidence is needed before strengths are ranked.</p>
            )}
          </div>
          <div className="panel">
            <SectionHeading eyebrow="WEAK AREAS" title="Critical gaps" />
            {readiness.data.critical_gaps.length ? (
              <div className="evidence-list">
                {readiness.data.critical_gaps.slice(0, 4).map((skill) => (
                  <div key={skill.competency_id}>
                    <Target size={17} />
                    <span>
                      <strong>{skill.name}</strong>
                      <small>{percent(skill.score)} readiness</small>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p>No critical gap is justified by the current evidence.</p>
            )}
          </div>
        </section>
      )}

      <section className="panel section-block">
        <SectionHeading
          eyebrow="QUESTION BANK"
          title="Recently published practice"
          aside={
            <Link className="text-link" href="/question-bank">
              View all <ArrowRight size={14} />
            </Link>
          }
        />
        {questions.isLoading && <LoadingState label="Loading published questions" />}
        {questions.isError && <ErrorState retry={() => void questions.refetch()} />}
        {questions.data?.items.length === 0 && (
          <p>No independently reviewed questions are published yet.</p>
        )}
        {questions.data && (
          <div className="compact-list">
            {questions.data.items.map((question) => (
              <Link href={`/question-bank/${question.slug}`} key={question.slug}>
                <span className="question-id">v{question.publication_version}</span>
                <strong>{question.title}</strong>
                <small>
                  {titleCaseSlug(question.track)} · {question.difficulty} ·{" "}
                  {question.estimated_duration_minutes} min
                </small>
                <ArrowRight size={15} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ManagementOverview() {
  return (
    <div className="page-content">
      <section className="hero hero--dashboard">
        <div>
          <span className="eyebrow">RIGOR PLATFORM ADMIN</span>
          <h1>Govern SkillsForge AI content and evidence.</h1>
          <p>
            Candidate experience remains separate from content administration. Use the
            management workspace for source review, publication, and release governance.
          </p>
          <div className="hero-actions">
            <Link className="button button--primary" href="/admin/questions">
              Manage content <ArrowRight size={16} />
            </Link>
            <Link className="button button--ghost" href="/content-review">
              Review queue
            </Link>
          </div>
        </div>
        <div className="release-gate">
          <span>BOUNDARY</span>
          <strong>RIGOR</strong>
          <p>Internal governance and administration for the SkillsForge AI product.</p>
        </div>
      </section>
    </div>
  );
}

export function Dashboard() {
  const { principal } = useAuth();
  const isCandidate = principal?.roles.includes("candidate") ?? false;
  return isCandidate ? <CandidateOverview /> : <ManagementOverview />;
}
