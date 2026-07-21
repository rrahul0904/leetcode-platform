import { ArrowUpRight, Clock3 } from "lucide-react";
import Link from "next/link";

import type { CatalogQuestion } from "@/lib/api";
import { titleCaseSlug } from "@/lib/product-data";

export function QuestionCard({ question }: { question: CatalogQuestion }) {
  return (
    <Link className="question-card" href={`/question-bank/${question.slug}`}>
      <div className="question-card__topline">
        <span className="practice-type practice-type--hosted">HOSTED</span>
        <span className={`difficulty difficulty--${question.difficulty}`}>
          {question.difficulty}
        </span>
      </div>
      <span className="question-id">
        {question.external_id} · v{question.publication_version}
      </span>
      <h3>{question.title}</h3>
      <p>
        {question.learning_objectives[0] ??
          "Practice this published interview skill."}
      </p>
      <div className="skill-row">
        {question.skills.slice(0, 3).map((skill) => (
          <span key={skill}>{skill}</span>
        ))}
      </div>
      <dl className="external-card__meta" aria-label="Practice capabilities">
        <div>
          <dt>Role level</dt>
          <dd>{titleCaseSlug(question.role_level)}</dd>
        </div>
        <div>
          <dt>Capabilities</dt>
          <dd>Hosted prompt · Workspace ready</dd>
        </div>
      </dl>
      <div className="question-card__footer">
        <span>{titleCaseSlug(question.track)}</span>
        <span>
          <Clock3 size={12} /> {question.estimated_duration_minutes} min
        </span>
        <ArrowUpRight size={14} />
      </div>
    </Link>
  );
}

export function QuestionCardSkeleton() {
  return (
    <div className="question-card question-card--loading" aria-hidden="true" />
  );
}
