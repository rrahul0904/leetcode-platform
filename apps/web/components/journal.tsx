import { ArrowRight, BookOpen, Clock3 } from "lucide-react";
import Link from "next/link";

import { journalArticles } from "@/lib/editorial-content";

export function Journal() {
  const [featured, ...articles] = journalArticles;

  if (!featured) return null;

  return (
    <div className="editorial-experience journal-page">
      <header className="editorial-hero">
        <span>RIGOR JOURNAL</span>
        <h1>
          Ideas for operating under <em>interview pressure.</em>
        </h1>
        <p>
          Essays on engineering judgment, technical communication, reliability,
          AI infrastructure, and the habits that make senior candidates credible.
        </p>
      </header>

      <main className="journal-content">
        <Link
          className={`journal-feature journal-accent--${featured.accent}`}
          href={`/journal/${featured.slug}`}
        >
          <div className="journal-feature__visual" aria-hidden="true">
            <span>01</span>
            <i />
            <BookOpen size={28} />
          </div>
          <div className="journal-feature__copy">
            <span>{featured.category}</span>
            <h2>{featured.title}</h2>
            <p>{featured.dek}</p>
            <footer>
              <span>{featured.publishedAt}</span>
              <span>
                <Clock3 size={12} /> {featured.readMinutes} min read
              </span>
              <strong>
                Read essay <ArrowRight size={14} />
              </strong>
            </footer>
          </div>
        </Link>

        <section className="journal-index">
          <div className="editorial-section-heading">
            <span>LATEST ESSAYS</span>
            <h2>Systems thinking, written for practice.</h2>
          </div>
          <div className="journal-grid">
            {articles.map((article, index) => (
              <Link
                className={`journal-card journal-accent--${article.accent}`}
                href={`/journal/${article.slug}`}
                key={article.slug}
              >
                <div className="journal-card__ribbon">
                  <span>{article.category}</span>
                  <i>{String(index + 2).padStart(2, "0")}</i>
                </div>
                <h3>{article.title}</h3>
                <p>{article.dek}</p>
                <footer>
                  <span>{article.publishedAt}</span>
                  <span>{article.readMinutes} min</span>
                  <ArrowRight size={14} />
                </footer>
              </Link>
            ))}
          </div>
        </section>
      </main>

      <footer className="editorial-taxonomy">
        <span>ENGINEERING SYSTEMS</span>
        <span>INTERVIEW CRAFT</span>
        <span>STAFF LEADERSHIP</span>
        <span>AI INFRASTRUCTURE</span>
      </footer>
    </div>
  );
}
