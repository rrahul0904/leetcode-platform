"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  FileCheck2,
  Link2,
  Route,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import {
  EvidenceNote,
  ErrorState,
  LoadingState,
  SectionHeading,
} from "@/components/page-ui";
import {
  getPracticeSummary,
  getProfile,
  getPublishedQuestions,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCaseSlug } from "@/lib/product-data";

const candidateDestinations = [
  [
    "Explore the bank",
    "Browse published hosted questions and the full external practice catalog.",
    "/question-bank",
    BookOpen,
  ],
  [
    "External practice",
    "Search source-backed references and continue to their canonical source.",
    "/external-practice",
    Link2,
  ],
  [
    "Choose a path",
    "Turn target-role intent into a transparent, staged preparation plan.",
    "/learning-paths",
    Route,
  ],
  [
    "Configure a mock",
    "Build a timed interview agenda before AI interviewing is connected.",
    "/mock-interviews",
    Sparkles,
  ],
] as const;

const administratorDestinations = [
  [
    "Manage content",
    "Create, import, and inspect the question library.",
    "/admin/questions",
    BookOpen,
  ],
  [
    "Review queue",
    "Assign reviewers and move approved questions toward publication.",
    "/content-review",
    FileCheck2,
  ],
  [
    "Manage sources",
    "Review source rights before enabling any connector.",
    "/admin/sources",
    ShieldCheck,
  ],
] as const;

export function Dashboard() {
  const { principal } = useAuth();
  const isCandidate = principal?.roles.includes("candidate") ?? false;
  const isAdministrator =
    principal?.roles.includes("platform-administrator") ?? false;
  const destinations = isAdministrator
    ? administratorDestinations
    : candidateDestinations;
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
    queryKey: ["published-questions", "dashboard-sample"],
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
          pageSize: 5,
        },
        signal,
      ),
  });

  return (
    <div className="page-content">
      <section className="hero hero--dashboard">
        <div>
          <span className="eyebrow">
            {isAdministrator ? "CONTENT OVERVIEW" : "INTERVIEW PRACTICE"}
          </span>
          <h1>
            {isAdministrator
              ? "Manage the question library."
              : "Prepare with a clear plan."}
          </h1>
          <p>
            {isAdministrator
              ? "Create, review, and publish high-quality interview questions from one workspace."
              : "Choose a path, practice published questions, and track real progress."}
          </p>
          <div className="hero-actions">
            <Link
              className="button button--primary"
              href={isAdministrator ? "/admin/questions" : "/question-bank"}
            >
              {isAdministrator ? "Manage content" : "Browse questions"}{" "}
              <ArrowRight size={16} />
            </Link>
            <Link
              className="button button--ghost"
              href={isAdministrator ? "/content-review" : "/learning-paths"}
            >
              {isAdministrator ? "Open review queue" : "Choose a learning path"}
            </Link>
          </div>
        </div>
        <div className="release-gate">
          <span>PUBLISHED HOSTED QUESTIONS</span>
          <strong>
            {stats.data?.published_hosted_questions ?? 0}
            <small> live</small>
          </strong>
          <div className="progress-track">
            <i
              style={{
                width: stats.data?.published_hosted_questions ? "100%" : "0%",
              }}
            />
          </div>
          <p>Continuous growth has no final question-count ceiling.</p>
        </div>
      </section>

      {stats.isError && <ErrorState retry={() => void stats.refetch()} />}
      {!stats.data && !stats.isError && (
        <LoadingState label="Reading content evidence" />
      )}
      {stats.data && (
        <>
          <section className="status-strip" aria-label="Question bank status">
            {[
              [
                "External references",
                stats.data.external_references,
                "canonical source links",
                "accent",
              ],
              [
                "Hosted records",
                stats.data.hosted_records,
                "original question packages",
                "",
              ],
              [
                "Awaiting review",
                stats.data.awaiting_review,
                "technical or editorial",
                "",
              ],
              [
                "Published hosted",
                stats.data.published_hosted_questions,
                "candidate-ready",
                "",
              ],
              [
                "Approved sources",
                stats.data.approved_sources,
                "collection permitted",
                "",
              ],
            ].map(([label, value, note, accent]) => (
              <div
                className={`stat ${accent ? "stat--accent" : ""}`}
                key={label}
              >
                <span>{label}</span>
                <strong>{Number(value).toLocaleString()}</strong>
                <small>{note}</small>
              </div>
            ))}
          </section>
        </>
      )}
      <EvidenceNote tone="warning">
        <strong>
          Hosted questions and external references are counted separately.
        </strong>
        <span>
          Only independently reviewed, currently published hosted versions
          appear as candidate practice.
        </span>
      </EvidenceNote>
      {stats.data && (
        <section className="panel source-counts section-block">
          <SectionHeading
            eyebrow="POSTGRESQL CATALOG"
            title="References by source"
            aside={
              <span className="status-chip">
                Last collection{" "}
                {stats.data.last_successful_collection
                  ? new Date(
                      stats.data.last_successful_collection,
                    ).toLocaleString()
                  : "not run"}
              </span>
            }
          />
          <div className="source-count-grid">
            {stats.data.source_counts.map((source) => (
              <Link href={`/external-practice`} key={source.source_id}>
                <span>{source.source_name}</span>
                <strong>{source.reference_count.toLocaleString()}</strong>
              </Link>
            ))}
          </div>
        </section>
      )}
      {profile.data && (
        <section className="personalization-strip">
          <div>
            <span>PRIMARY TARGET</span>
            <strong>{profile.data.target_roles[0]}</strong>
          </div>
          <div>
            <span>STUDY CAPACITY</span>
            <strong>{profile.data.weekly_study_hours} hours / week</strong>
          </div>
          <div>
            <span>INTENSITY</span>
            <strong>{profile.data.preparation_intensity}</strong>
          </div>
          <div>
            <span>INTERVIEW DATE</span>
            <strong>{profile.data.interview_date ?? "Not provided"}</strong>
          </div>
          <Link href="/onboarding">
            Edit profile <ArrowRight size={14} />
          </Link>
        </section>
      )}
      {isCandidate && profile.isError && (
        <section className="assignment-ready">
          <Route size={20} />
          <div>
            <strong>Personalize your preparation plan</strong>
            <p>Add your target role and study schedule when you are ready.</p>
          </div>
          <Link className="button button--ghost" href="/onboarding">
            Set up profile
          </Link>
        </section>
      )}

      <section className="dashboard-grid section-block">
        <div className="panel panel--wide">
          <SectionHeading eyebrow="NEXT STEP" title="What do you want to do?" />
          <div className="destination-grid">
            {destinations.map(([title, description, href, Icon]) => (
              <Link className="destination-card" href={href} key={href}>
                <Icon size={21} />
                <strong>{title}</strong>
                <p>{description}</p>
                <span>
                  Open <ArrowRight size={14} />
                </span>
              </Link>
            ))}
          </div>
        </div>
        <div className="panel">
          <SectionHeading eyebrow="GOVERNANCE" title="Release evidence" />
          <div className="evidence-list">
            <div>
              <ShieldCheck size={17} />
              <span>
                <strong>12 publication gates</strong>
                <small>4 evidenced on the first draft</small>
              </span>
            </div>
            <div>
              <FileCheck2 size={17} />
              <span>
                <strong>Independent approvals</strong>
                <small>technical + editorial required</small>
              </span>
            </div>
            <div>
              <BookOpen size={17} />
              <span>
                <strong>Immutable versions</strong>
                <small>candidate history keeps its source</small>
              </span>
            </div>
          </div>
          <Link className="text-link" href="/quality-gates">
            Inspect quality gates <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="panel section-block">
        <SectionHeading
          eyebrow="HOSTED CATALOG"
          title="Recently published questions"
          aside={
            <Link className="text-link" href="/question-bank">
              View all <ArrowRight size={14} />
            </Link>
          }
        />
        {questions.data?.items.length === 0 && (
          <p>No independently reviewed hosted questions are published yet.</p>
        )}
        {questions.data && (
          <div className="compact-list">
            {questions.data.items.map((question) => (
              <Link
                href={`/question-bank/${question.slug}`}
                key={question.slug}
              >
                <span className="question-id">
                  v{question.publication_version}
                </span>
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
