"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { getKnowledgeCompanies } from "@/lib/knowledge-api";

export function KnowledgeCompanies() {
  const [query, setQuery] = useState("");
  const companies = useQuery({
    queryKey: ["knowledge-companies"],
    queryFn: ({ signal }) => getKnowledgeCompanies(signal),
  });
  const filtered = (companies.data ?? []).filter((company) =>
    company.name.casefold ? company.name : company.name,
  );
  const visible = filtered.filter((company) =>
    company.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  );

  return (
    <div className="kb-page kb-collection-page">
      <section className="kb-hero">
        <div>
          <span className="kb-eyebrow">COMPANY PREPARATION</span>
          <h1>Prepare by evidence, not rumor.</h1>
          <p>
            Company records are connected to canonical problems and retain their source
            window, frequency, difficulty, and observation provenance.
          </p>
        </div>
      </section>
      <label className="kb-search kb-collection-search">
        <Search size={17} />
        <input
          aria-label="Search companies"
          placeholder="Search company indexes"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {companies.isLoading && <div className="kb-workspace-loading">Loading companies…</div>}
      {companies.isError && <div className="kb-workspace-loading">Company data is unavailable.</div>}
      <section className="kb-company-grid">
        {visible.map((company) => (
          <Link href={`/problems?company=${company.slug}&sort=frequency`} key={company.id}>
            <Building2 size={20} />
            <span>COMPANY INDEX</span>
            <h2>{company.name}</h2>
            <strong>{company.problem_count.toLocaleString()} problems</strong>
            <div>
              <small>{company.easy_count} easy</small>
              <small>{company.medium_count} medium</small>
              <small>{company.hard_count} hard</small>
            </div>
            <p>
              {company.average_frequency == null
                ? "Frequency varies by source window."
                : `Average recorded frequency ${company.average_frequency.toFixed(1)}.`}
            </p>
            <em>Open preparation list <ArrowRight size={14} /></em>
          </Link>
        ))}
      </section>
    </div>
  );
}
