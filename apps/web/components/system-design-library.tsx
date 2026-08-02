"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Boxes, Network, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { getSystemDesignLibrary } from "@/lib/knowledge-api";

export function SystemDesignLibrary() {
  const [query, setQuery] = useState("");
  const articles = useQuery({
    queryKey: ["knowledge-system-design"],
    queryFn: ({ signal }) => getSystemDesignLibrary(signal),
  });
  const visible = (articles.data ?? []).filter((article) =>
    article.title.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  );

  return (
    <div className="kb-page kb-collection-page">
      <section className="kb-hero">
        <div>
          <span className="kb-eyebrow">SYSTEM DESIGN LIBRARY</span>
          <h1>Design from requirements to failure recovery.</h1>
          <p>
            Reviewed architecture material is organized as concepts, components, data
            flows, capacity assumptions, trust boundaries, and interview follow-ups.
          </p>
        </div>
        <Link className="kb-primary-action" href="/mock-interviews">
          Start design mock <ArrowRight size={16} />
        </Link>
      </section>
      <label className="kb-search kb-collection-search">
        <Search size={17} />
        <input
          aria-label="Search system design"
          placeholder="Search systems, concepts, and architecture patterns"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {articles.isLoading && <div className="kb-workspace-loading">Loading system-design material…</div>}
      {articles.isError && <div className="kb-workspace-loading">System-design material is unavailable.</div>}
      {articles.data && visible.length === 0 && (
        <div className="kb-workspace-loading">
          No reviewed system-design article matches this search.
        </div>
      )}
      <section className="kb-design-grid">
        {visible.map((article, index) => (
          <Link href={`/system-design-library/${article.slug}`} key={article.id}>
            <div>
              {index % 2 === 0 ? <Network size={22} /> : <Boxes size={22} />}
              <span>DESIGN NOTE {String(index + 1).padStart(2, "0")}</span>
            </div>
            <h2>{article.title}</h2>
            <p>{article.headings.slice(1, 4).join(" · ") || "Architecture analysis and trade-offs"}</p>
            <small>{article.image_count} referenced diagrams</small>
            <em>Study this system <ArrowRight size={14} /></em>
          </Link>
        ))}
      </section>
    </div>
  );
}
