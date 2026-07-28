"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Clock3,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/page-ui";
import { getPublishedQuestion } from "@/lib/api";
import { titleCaseSlug } from "@/lib/product-data";

export function QuestionDetail({ slug }: { slug: string }) {
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
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
          {item.starter_code?.trimStart().startsWith("def ") && (
            <Link className="button button--primary" href={`/practice/${slug}`}>
              Start practice <ArrowRight size={16} />
            </Link>
          )}
          {item.starter_code?.trimStart().startsWith("class ") && (
            <p className="boundary-note">
              Class-style execution is not enabled in the current Python
              runner milestone. The prompt remains available for guided study.
            </p>
          )}
        </div>
        <aside className="availability-card">
          <ShieldCheck size={22} />
          <span>PUBLICATION</span>
          <strong>Published</strong>
          <p>This candidate view is projected from public fields only.</p>
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
