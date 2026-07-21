"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  FileCheck2,
  FileUp,
  Plus,
  Radar,
} from "lucide-react";
import Link from "next/link";

import {
  ErrorState,
  LoadingState,
  PageHeader,
  SectionHeading,
} from "@/components/page-ui";
import {
  getContentImports,
  getContinuousCoverage,
  getQuestionIntelligence,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const primaryActions = [
  [
    "Generate a batch",
    "Validate up to ten complete question packages.",
    "/admin/questions/new",
    Plus,
  ],
  [
    "Import content",
    "Validate a JSON, JSONL, CSV, or ZIP package.",
    "/admin/content/import",
    FileUp,
  ],
  [
    "Review queue",
    "Move validated drafts through independent review.",
    "/content-review",
    FileCheck2,
  ],
  [
    "Coverage gaps",
    "See which competencies need original questions.",
    "/admin/questions/gaps",
    Radar,
  ],
] as const;

const libraryLinks = [
  ["Question library", "/admin/questions/library"],
  ["Duplicates", "/admin/questions/duplicates"],
  ["Families", "/admin/questions/families"],
  ["Variants", "/admin/questions/variants"],
  ["Freshness", "/admin/questions/freshness"],
  ["Rights", "/admin/questions/licenses"],
  ["Provenance", "/admin/questions/provenance"],
] as const;

export function ContentHub() {
  const { principal } = useAuth();
  const canImport = principal?.permissions.includes("content:import") ?? false;
  const canReview = principal?.permissions.includes("review:read") ?? false;
  const canReadCoverage =
    principal?.permissions.includes("coverage:read") ?? false;
  const coverage = useQuery({
    queryKey: ["continuous-coverage"],
    queryFn: ({ signal }) => getContinuousCoverage(signal),
    enabled: canReadCoverage,
  });
  const questions = useQuery({
    queryKey: ["question-intelligence", "questions"],
    queryFn: ({ signal }) => getQuestionIntelligence("questions", signal),
  });
  const imports = useQuery({
    queryKey: ["content-imports"],
    queryFn: ({ signal }) => getContentImports(signal),
    enabled: canImport,
  });
  if (
    (canReadCoverage && coverage.isLoading) ||
    questions.isLoading ||
    (canImport && imports.isLoading)
  )
    return (
      <div className="page-content">
        <LoadingState label="Loading content workspace" />
      </div>
    );
  if (
    (canReadCoverage && coverage.isError) ||
    questions.isError ||
    (canImport && imports.isError)
  )
    return (
      <div className="page-content">
        <ErrorState retry={() => window.location.reload()} />
      </div>
    );
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="CONTENT"
        title="Manage the question library."
        description="Create, import, review, and publish questions from one place."
      />
      <section className="status-strip" aria-label="Content status">
        <div className="stat stat--accent">
          <span>Drafts</span>
          <strong>{questions.data?.length ?? 0}</strong>
          <small>hosted records</small>
        </div>
        <div className="stat">
          <span>Published</span>
          <strong>{coverage.data?.published_questions ?? "—"}</strong>
          <small>visible to candidates</small>
        </div>
        <div className="stat">
          <span>Open gaps</span>
          <strong>{coverage.data?.open_coverage_gaps ?? "—"}</strong>
          <small>need authoring</small>
        </div>
        <div className="stat">
          <span>Recent imports</span>
          <strong>{imports.data?.length ?? "—"}</strong>
          <small>validation runs</small>
        </div>
      </section>
      <section className="panel section-block">
        <SectionHeading eyebrow="START HERE" title="What do you want to do?" />
        <div className="destination-grid">
          {primaryActions
            .filter(([, , href]) => {
              if (href === "/admin/content/import") return canImport;
              if (href === "/content-review") return canReview;
              if (href === "/admin/questions/gaps") return canReadCoverage;
              return true;
            })
            .map(([title, description, href, Icon]) => (
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
      </section>
      <section className="panel section-block">
        <SectionHeading
          eyebrow="LIBRARY TOOLS"
          title="Inspect and maintain content"
        />
        <div className="compact-list">
          {libraryLinks.map(([label, href]) => (
            <Link href={href} key={href}>
              <BookOpen size={16} />
              <strong>{label}</strong>
              <ArrowRight size={15} />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
