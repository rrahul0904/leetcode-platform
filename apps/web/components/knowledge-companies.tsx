"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  getKnowledgeCompanies,
  getKnowledgeCompanyReadiness,
  type CompanySummary,
} from "@/lib/knowledge-api";

import styles from "./knowledge-companies.module.css";

type CompanySort = "readiness" | "problems" | "frequency" | "name";

function compareCompanies(
  left: CompanySummary,
  right: CompanySummary,
  sort: CompanySort,
  readiness: Map<string, number>,
) {
  if (sort === "name") return left.name.localeCompare(right.name);
  if (sort === "frequency") {
    return (
      (right.average_frequency ?? -1) - (left.average_frequency ?? -1) ||
      right.problem_count - left.problem_count ||
      left.name.localeCompare(right.name)
    );
  }
  if (sort === "readiness") {
    return (
      (readiness.get(right.slug) ?? 0) - (readiness.get(left.slug) ?? 0) ||
      right.problem_count - left.problem_count ||
      left.name.localeCompare(right.name)
    );
  }
  return right.problem_count - left.problem_count || left.name.localeCompare(right.name);
}

export function KnowledgeCompanies() {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<CompanySort>("problems");
  const companies = useQuery({
    queryKey: ["knowledge-companies"],
    queryFn: ({ signal }) => getKnowledgeCompanies(signal),
  });
  const companyReadiness = useQuery({
    queryKey: ["knowledge-company-readiness"],
    queryFn: ({ signal }) => getKnowledgeCompanyReadiness(signal),
  });

  const readinessBySlug = useMemo(
    () => new Map((companyReadiness.data ?? []).map((item) => [item.slug, item])),
    [companyReadiness.data],
  );
  const completionBySlug = useMemo(
    () =>
      new Map(
        (companyReadiness.data ?? []).map((item) => [item.slug, item.completion_percent]),
      ),
    [companyReadiness.data],
  );
  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return [...(companies.data ?? [])]
      .filter((company) => company.name.toLocaleLowerCase().includes(normalized))
      .sort((left, right) => compareCompanies(left, right, sort, completionBySlug));
  }, [companies.data, completionBySlug, query, sort]);

  return (
    <div className="kb-page kb-collection-page">
      <section className="kb-hero">
        <div>
          <span className="kb-eyebrow">COMPANY INTELLIGENCE</span>
          <h1>Prepare by evidence, not rumor.</h1>
          <p>
            Explore source-backed company observations, rank the highest-signal preparation
            pools, and track your own coverage as you solve canonical problems.
          </p>
        </div>
      </section>

      <div className={styles.toolbar}>
        <label className="kb-search kb-collection-search">
          <Search size={17} />
          <input
            aria-label="Search companies"
            placeholder="Search company indexes"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <select
          aria-label="Sort companies"
          className={styles.sort}
          value={sort}
          onChange={(event) => setSort(event.target.value as CompanySort)}
        >
          <option value="problems">Most observations</option>
          <option value="readiness">Most prepared</option>
          <option value="frequency">Highest frequency</option>
          <option value="name">Company name</option>
        </select>
      </div>

      <p className={styles.context}>
        Company associations reflect imported observation evidence and source windows. They
        are preparation signals, not a guarantee that a problem was asked in a specific
        interview. Your readiness score is simply solved observed problems divided by the
        visible observed problem set for that company.
      </p>

      {companies.isLoading && <div className="kb-workspace-loading">Loading companies…</div>}
      {companies.isError && <div className="kb-workspace-loading">Company data is unavailable.</div>}
      {companyReadiness.isError && !companies.isError && (
        <div className="kb-workspace-loading">
          Company indexes are available, but personal readiness could not be loaded.
        </div>
      )}

      <section className="kb-company-grid">
        {visible.map((company) => {
          const progress = readinessBySlug.get(company.slug);
          const completion = progress?.completion_percent ?? 0;
          const problemCount = progress?.problem_count ?? company.problem_count;
          return (
            <Link
              className={styles.card}
              href={`/problems?company=${company.slug}&sort=frequency`}
              key={company.id}
            >
              <div className={styles.cardHeader}>
                <Building2 size={20} />
                <span>COMPANY INDEX</span>
              </div>
              <h2>{company.name}</h2>
              <strong>{problemCount.toLocaleString()} observed problems</strong>
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

              <div className={styles.readiness}>
                <div className={styles.readinessHeader}>
                  <span>Preparation coverage</span>
                  <strong>{completion.toFixed(1)}%</strong>
                </div>
                <div
                  aria-label={`${company.name} preparation coverage ${completion.toFixed(1)} percent`}
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={completion}
                  className={styles.track}
                  role="progressbar"
                >
                  <span style={{ width: `${completion}%` }} />
                </div>
                <div className={styles.progressStats}>
                  <small>
                    <b>{progress?.solved_count ?? 0}</b>
                    <i>Solved</i>
                  </small>
                  <small>
                    <b>{progress?.in_progress_count ?? 0}</b>
                    <i>In progress</i>
                  </small>
                  <small>
                    <b>{progress?.remaining_count ?? problemCount}</b>
                    <i>Remaining</i>
                  </small>
                </div>
              </div>

              <em>
                Open ranked preparation list <ArrowRight size={14} />
              </em>
            </Link>
          );
        })}
        {!companies.isLoading && !companies.isError && visible.length === 0 && (
          <div className={styles.empty}>No company index matches that search.</div>
        )}
      </section>
    </div>
  );
}
