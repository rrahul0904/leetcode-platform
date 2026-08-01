"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Boxes, Clock3, Network } from "lucide-react";
import Link from "next/link";

import { getSystemDesignArticle } from "@/lib/knowledge-api";

export function SystemDesignArticle({ slug }: { slug: string }) {
  const article = useQuery({
    queryKey: ["knowledge-system-design", slug],
    queryFn: ({ signal }) => getSystemDesignArticle(slug, signal),
  });

  if (article.isLoading) {
    return <div className="kb-workspace-loading">Loading architecture material…</div>;
  }
  if (article.isError || !article.data) {
    return (
      <div className="kb-workspace-loading">
        <strong>This system-design article could not be opened.</strong>
        <Link href="/system-design-library">Return to the library</Link>
      </div>
    );
  }

  const item = article.data;
  const sections = item.body
    .split(/\n(?=#{1,6}\s)/)
    .map((section) => section.trim())
    .filter(Boolean);

  return (
    <div className="kb-design-article">
      <aside>
        <Link href="/system-design-library">
          <ArrowLeft size={14} /> System design
        </Link>
        <span>ARTICLE MAP</span>
        <nav>
          {item.headings.slice(0, 20).map((heading, index) => (
            <a href={`#section-${index}`} key={`${heading}-${index}`}>
              <i>{String(index + 1).padStart(2, "0")}</i>
              {heading}
            </a>
          ))}
        </nav>
      </aside>
      <main>
        <header>
          <span className="kb-eyebrow">SYSTEM DESIGN STUDY NOTE</span>
          <h1>{item.title}</h1>
          <div>
            <small><Network size={14} /> {item.headings.length} sections</small>
            <small><Boxes size={14} /> {item.image_count} diagrams</small>
            <small><Clock3 size={14} /> Self-paced</small>
          </div>
        </header>
        {sections.map((section, index) => {
          const lines = section.splitlines ? [] : section.split("\n");
          const heading = lines[0]?.replace(/^#{1,6}\s*/, "") || item.headings[index] || "Overview";
          const body = lines.slice(1).join("\n").trim();
          return (
            <section id={`section-${index}`} key={index}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h2>{heading}</h2>
              <pre>{body || section}</pre>
            </section>
          );
        })}
      </main>
    </div>
  );
}
