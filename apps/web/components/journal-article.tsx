import { ArrowLeft, ArrowRight, Clock3 } from "lucide-react";
import Link from "next/link";

import type { JournalArticle } from "@/lib/editorial-content";
import { journalArticles } from "@/lib/editorial-content";

export function JournalArticleView({ article }: { article: JournalArticle }) {
  const related = journalArticles
    .filter((candidate) => candidate.slug !== article.slug)
    .slice(0, 2);

  return (
    <article className="editorial-experience article-page">
      <header className={`article-hero journal-accent--${article.accent}`}>
        <Link href="/journal">
          <ArrowLeft size={14} /> Back to journal
        </Link>
        <div className="article-hero__meta">
          <span>{article.category}</span>
          <span>{article.publishedAt}</span>
          <span>
            <Clock3 size={12} /> {article.readMinutes} min read
          </span>
        </div>
        <h1>{article.title}</h1>
        <p>{article.dek}</p>
      </header>

      <div className="article-layout">
        <nav className="article-outline" aria-label="Article outline">
          <span>IN THIS ESSAY</span>
          {article.sections.map((section, index) => (
            <a href={`#section-${index + 1}`} key={section.heading}>
              <i>{String(index + 1).padStart(2, "0")}</i>
              {section.heading}
            </a>
          ))}
        </nav>

        <main className="article-reading-column">
          <p className="article-lead">{article.lead}</p>
          {article.sections.map((section, index) => (
            <section id={`section-${index + 1}`} key={section.heading}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
              {section.code && (
                <pre aria-label={`${section.heading} code example`}>
                  <code>{section.code}</code>
                </pre>
              )}
            </section>
          ))}

          <div className="article-conclusion">
            <span>PRACTICE PROMPT</span>
            <p>
              Explain the central decision from this essay in two minutes. Name the
              invariant, the rejected alternative, and the evidence you would collect.
            </p>
            <Link href="/mock-interviews">
              Practice under time <ArrowRight size={14} />
            </Link>
          </div>
        </main>
      </div>

      <section className="article-related">
        <div className="editorial-section-heading">
          <span>CONTINUE READING</span>
          <h2>Related operating ideas.</h2>
        </div>
        <div>
          {related.map((candidate) => (
            <Link href={`/journal/${candidate.slug}`} key={candidate.slug}>
              <span>{candidate.category}</span>
              <h3>{candidate.title}</h3>
              <p>{candidate.dek}</p>
              <strong>
                Read essay <ArrowRight size={13} />
              </strong>
            </Link>
          ))}
        </div>
      </section>
    </article>
  );
}
