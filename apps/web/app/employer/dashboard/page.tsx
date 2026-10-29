"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  getEmployerAssessmentReport,
  listEmployerAssessments,
  selectedEmployerOrganization,
  type EmployerAssessment,
  type EmployerAssessmentReport,
} from "@/lib/employer-assessment-api";

type DashboardData = {
  assessments: EmployerAssessment[];
  reports: Record<string, EmployerAssessmentReport>;
  unavailableReports: number;
};

function Metric({ label, value, detail }: { label: string; value: number | string; detail: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-3 text-3xl font-bold tracking-tight text-slate-950">{value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
    </div>
  );
}

export default function EmployerDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [organizationSelected, setOrganizationSelected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const selected = selectedEmployerOrganization();
      setOrganizationSelected(Boolean(selected));
      if (!selected) {
        setData(null);
        return;
      }
      const assessments = await listEmployerAssessments();
      const published = assessments.filter((assessment) => assessment.status === "published");
      const results = await Promise.allSettled(
        published.map((assessment) => getEmployerAssessmentReport(assessment.id)),
      );
      const reports: Record<string, EmployerAssessmentReport> = {};
      let unavailableReports = 0;
      results.forEach((result, index) => {
        const assessment = published[index];
        if (!assessment) return;
        if (result.status === "fulfilled") {
          reports[assessment.id] = result.value;
        } else {
          unavailableReports += 1;
        }
      });
      setData({ assessments, reports, unavailableReports });
    } catch (cause) {
      setData(null);
      setError(cause instanceof Error ? cause.message : "Unable to load employer dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const publishedCount = data?.assessments.filter((assessment) => assessment.status === "published").length ?? 0;
  const draftCount = data?.assessments.filter((assessment) => assessment.status !== "published").length ?? 0;
  const complete = data !== null && data.unavailableReports === 0;
  const totals = useMemo(() => {
    const reports = Object.values(data?.reports ?? {});
    return reports.reduce(
      (total, report) => ({
        invited: total.invited + report.total_invitations,
        submitted: total.submitted + report.submitted_attempts,
        reviewed: total.reviewed + report.human_reviewed_attempts,
      }),
      { invited: 0, submitted: 0, reviewed: 0 },
    );
  }, [data]);

  return (
    <main className="mx-auto max-w-[1440px] space-y-7 px-4 py-8 sm:px-6 lg:px-8">
      <header className="overflow-hidden rounded-3xl bg-slate-950 p-6 text-white sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-300">
              SkillForge / Employer command center
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Hiring assessments</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">
              Build assessments, invite candidates and review submitted work.
              Metrics come from the selected employer organization—not demo fixtures.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/employer/assessments"
              className="rounded-xl bg-sky-500 px-4 py-3 text-sm font-bold text-slate-950 hover:bg-sky-400">
              Create assessment
            </Link>
            <Link href="/employer"
              className="rounded-xl border border-slate-600 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800">
              Switch organization
            </Link>
          </div>
        </div>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
          {error}
        </div>
      )}
      {!organizationSelected && !loading && (
        <section className="rounded-2xl border border-slate-200 bg-white p-8">
          <h2 className="text-xl font-bold">Choose an employer workspace first</h2>
          <p className="mt-2 text-sm text-slate-600">
            Reports are always scoped to an organization that you can access.
            Select it before opening the command center.
          </p>
          <Link href="/employer" className="mt-4 inline-block rounded-lg bg-sky-600 px-4 py-3 text-sm font-semibold text-white">
            Select organization
          </Link>
        </section>
      )}
      {loading && <p role="status" className="text-sm text-slate-600">Loading authorized employer data…</p>}

      {data && (
        <>
          {!complete && (
            <p role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              Reporting is unavailable for {data.unavailableReports} published assessment(s).
              Totals below cover only the successfully loaded assessments.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Employer assessment metrics">
            <Metric label="Published" value={publishedCount} detail="Assessments accepting authorized invitations" />
            <Metric label="Draft / review" value={draftCount} detail="Require independent publication approval" />
            <Metric label="Invitations" value={totals.invited} detail={complete ? "Across published assessments" : "Verified subset only"} />
            <Metric label="Submitted" value={totals.submitted} detail={complete ? "Candidate assessment attempts" : "Verified subset only"} />
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
                <div>
                  <h2 className="text-xl font-bold text-slate-950">Assessment pipeline</h2>
                  <p className="mt-1 text-xs text-slate-500">Published and draft versions from this organization</p>
                </div>
                <button type="button" onClick={() => void load()} disabled={loading}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40">
                  Refresh
                </button>
              </div>
              {data.assessments.length === 0 ? (
                <div className="p-8 text-sm text-slate-600">
                  No assessments created yet. Build your first technical assessment to start a hiring pipeline.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th scope="col" className="p-4">Assessment</th>
                        <th scope="col" className="p-4">State</th>
                        <th scope="col" className="p-4 text-right">Submitted</th>
                        <th scope="col" className="p-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.assessments.map((assessment) => (
                        <tr key={assessment.id}>
                          <td className="p-4">
                            <p className="font-semibold text-slate-900">{assessment.title}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              v{assessment.version} · {assessment.questions.length} questions · {assessment.duration_minutes} min
                            </p>
                          </td>
                          <td className="p-4">
                            <span className={
                              "inline-flex rounded-full px-3 py-1 text-xs font-semibold " +
                              (assessment.status === "published"
                                ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800")
                            }>{assessment.status.replaceAll("_", " ")}</span>
                          </td>
                          <td className="p-4 text-right font-mono text-slate-800">
                            {data.reports[assessment.id]?.submitted_attempts ?? "—"}
                          </td>
                          <td className="p-4 text-right">
                            <Link href={assessment.status === "published" ? "/employer/reviews" : "/employer/assessments"}
                              className="font-semibold text-sky-700 hover:underline">
                              {assessment.status === "published" ? "Review" : "Edit"}
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <aside className="space-y-4">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-lg font-bold text-slate-950">Review operations</h2>
                <p className="mt-2 text-sm text-slate-600">
                  {totals.reviewed} submitted attempt(s) with human review evidence.
                </p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"
                  role="progressbar" aria-label="Share of submissions with human reviews"
                  aria-valuemin={0} aria-valuemax={100}
                  aria-valuenow={totals.submitted ? Math.min(100, Math.round(totals.reviewed / totals.submitted * 100)) : 0}>
                  <div className="h-full rounded-full bg-sky-600"
                    style={{ width: (totals.submitted ? Math.min(100, Math.round(totals.reviewed / totals.submitted * 100)) : 0) + "%" }} />
                </div>
                <Link href="/employer/reviews"
                  className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white">
                  Open human review
                </Link>
              </section>
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-lg font-bold text-slate-950">Assessment integrity</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Server-bound answers, isolated code execution, confidential hidden tests,
                  and human-only hiring decisions.
                </p>
                <p className="mt-3 text-xs text-slate-500">
                  Integrity indicators are evidence for manual investigation, never an automatic accusation.
                </p>
              </section>
            </aside>
          </div>
        </>
      )}
    </main>
  );
}
