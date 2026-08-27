"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  Building2,
  Clock3,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/page-ui";
import { getPublishedQuestion } from "@/lib/api";
import { getExecutionCapability } from "@/lib/execution-capability";
import { titleCaseSlug } from "@/lib/product-data";

function runtimeLabel(runtime: "python3.13" | "postgresql18" | null) {
  if (runtime === "python3.13") return "Python 3.13";
  if (runtime === "postgresql18") return "PostgreSQL 18";
  return "Not executable";
}

export function QuestionDetail({ slug }: { slug: string }) {
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });
  const capability = useQuery({
    queryKey: ["execution-capability", slug],
    queryFn: ({ signal }) => getExecutionCapability(slug, signal),
  });
  if (question.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Loading published question" />
      </div>
    );
  if (question.isError || !question.data)
    return (
      <div className="page-content">
        <ErrorState retry={() => void question.refetch()} />
      </div>
    );
  const item = question.data;
  const canPractice = capability.data?.availability === "runnable";
  return (
    <div className="page-content">
      <Link className="back-link" href="/question-bank">
        <ArrowLeft size={15} /> Back to question bank
      </Link>
      <section className="detail-hero">
        <div>
          <div className="question-card__topline">
            <span className="question-id">
              {item.external_id} · Version {item.publication_version}
            </span>
            <span className={`difficulty difficulty--${item.difficulty}`}>
              {item.difficulty}
            </span>
          </div>
          <h1>{item.title}</h1>
          <p>{item.learning_objectives[0]}</p>
          <div className="skill-row skill-row--large">
            {item.skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
          <div className="detail-actions">
            {canPractice && (
              <Link className="button button--primary" href={`/practice/${slug}`}>
                Start practice <ArrowRight size={16} />
              </Link>
            )}
            <Link
              className="button button--secondary"
              href={`/question-bank/${slug}/solution`}
            >
              <BookOpenCheck size={16} /> Review solution
            </Link>
          </div>
          {capability.isLoading && (
            <p className="boundary-note">Checking isolated execution availability…</p>
          )}
          {capability.isError && (
            <p className="boundary-note">
              Execution availability could not be verified. Practice is disabled
              until the backend capability check succeeds.
            </p>
          )}
          {capability.data?.availability === "hosted" && (
            <p className="boundary-note">
              {capability.data.reason ??
                "This published question is currently available for guided study only."}
            </p>
          )}
        </div>
        <aside className="availability-card">
          <ShieldCheck size={22} />
          <span>EXECUTION</span>
          <strong>
            {capability.data?.availability === "runnable"
              ? "Runnable"
              : capability.isLoading
                ? "Checking"
                : "Hosted study"}
          </strong>
          <p>
            {capability.data
              ? `${runtimeLabel(capability.data.runtime)} · ${capability.data.public_test_count} public · ${capability.data.hidden_test_count} hidden tests`
              : "The server decides whether this exact published version can execute."}
          </p>
          <Link href="/quality-gates">View the release gates</Link>
        </aside>
      </section>
      <section className="detail-grid section-block">
        <div className="panel panel--wide">
          <span className="eyebrow">PROBLEM</span>
          <h2>Candidate prompt</h2>
          <p className="lead-copy">{item.problem_statement}</p>
          <h3>Instructions</h3>
          <ul>
            {item.candidate_instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ul>
          <h3>Public constraints</h3>
          <ul>
            {item.public_constraints.map((constraint) => (
              <li key={constraint}>{constraint}</li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <span className="eyebrow">INTERVIEW SHAPE</span>
          <dl className="metadata-list">
            <div>
              <dt>
                <Clock3 size={15} /> Duration
              </dt>
              <dd>{item.estimated_duration_minutes} minutes</dd>
            </div>
            <div>
              <dt>
                <Target size={15} /> Track
              </dt>
              <dd>{titleCaseSlug(item.track)}</dd>
            </div>
            <div>
              <dt>
                <Users size={15} /> Expected level
              </dt>
              <dd>{titleCaseSlug(item.role_level)}</dd>
            </div>
            <div>
              <dt>
                <Building2 size={15} /> Style relevance
              </dt>
              <dd>
                {item.company_style_tags.map(titleCaseSlug).join(", ") ||
                  "General interview"}
              </dd>
            </div>
          </dl>
        </div>
      </section>
      <section className="panel section-block">
        <span className="eyebrow">PUBLIC EXAMPLES</span>
        {item.public_examples.length === 0 ? (
          <p>No public examples were supplied for this discussion question.</p>
        ) : (
          item.public_examples.map((example) => (
            <div className="boundary-note" key={example.id}>
              <strong>{example.name}</strong>
              <pre>
                {JSON.stringify(
                  {
                    input: example.input,
                    expected_output: example.expected_output,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          ))
        )}
      </section>
      {item.starter_code && (
        <section className="panel section-block">
          <span className="eyebrow">STARTER CODE</span>
          <h2>Begin your implementation</h2>
          <pre className="starter-code">
            <code>{item.starter_code}</code>
          </pre>
        </section>
      )}
    </div>
  );
}
