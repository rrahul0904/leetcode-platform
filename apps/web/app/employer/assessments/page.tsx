"use client";

import { useEffect, useState } from "react";

import {
  createEmployerAssessment,
  inviteEmployerCandidate,
  listEmployerAssessments,
  publishEmployerAssessment,
  type EmployerAssessment,
  type EmployerInvitation,
} from "@/lib/employer-assessment-api";

export default function EmployerAssessmentsPage() {
  const [assessments, setAssessments] = useState<EmployerAssessment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [prompt, setPrompt] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [evidence, setEvidence] = useState("");
  const [invitation, setInvitation] = useState<EmployerInvitation | null>(null);

  async function refresh() {
    try {
      const response = await listEmployerAssessments();
      setAssessments(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot read employer assessments.");
    }
  }

  useEffect(() => {
    let active = true;
    void listEmployerAssessments()
      .then((items) => {
        if (active) setAssessments(items);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Cannot load assessments.");
        }
      });
    return () => { active = false; };
  }, []);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await createEmployerAssessment({
        slug: slug.trim(),
        title: title.trim(),
        duration_minutes: 60,
        questions: [{
          number: 1,
          kind: "written",
          prompt: prompt.trim(),
          marks: 100,
          options: [],
        }],
      });
      setNotice("Draft " + response.slug + " created. An independent reviewer must approve it.");
      setTitle("");
      setSlug("");
      setPrompt("");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot create assessment.");
    } finally {
      setBusy(false);
    }
  }

  async function publish(id: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await publishEmployerAssessment(id, {
        rights_evidence: evidence.trim(),
        technical_evidence: evidence.trim(),
        editorial_evidence: evidence.trim(),
      });
      setNotice("Published after independent reviewer attestation.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot approve assessment.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(id: string) {
    if (busy || !candidateId.trim()) return;
    setBusy(true);
    setError("");
    setInvitation(null);
    try {
      const response = await inviteEmployerCandidate(id, candidateId.trim(), 24);
      setInvitation(response);
      setNotice("Invitation created. Copy the secret once; it is not retained in this page.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot invite candidate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wider text-sky-500">
          SkillForge / Rigor · Organization workspace
        </p>
        <h1 className="mt-2 text-3xl font-semibold">Technical Assessments</h1>
        <p className="mt-2 max-w-3xl text-sm opacity-70">
          Build original technical screens, request independent approval and invite registered
          candidates. Your selected authenticated organization determines access.
          Unreviewed content cannot be sent to candidates.
        </p>
      </header>

      {error && <p role="alert" className="rounded-lg border border-red-500 p-3">{error}</p>}
      {notice && <p role="status" className="rounded-lg border border-sky-500 p-3">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <section className="space-y-4 rounded-2xl border p-6">
          <h2 className="text-xl font-semibold">Assessment inventory</h2>
          <p className="text-sm opacity-70">
            Assessment authoring currently supports an initial one-question written draft.
            Coding execution and multi-question visual authoring require the next release gates.
          </p>
          <button
            onClick={() => void refresh()}
            type="button"
            disabled={busy}
            className="rounded-lg border px-4 py-2 text-sm"
          >
            Refresh
          </button>
          {assessments.length === 0 && (
            <p className="rounded-xl border p-5 text-sm opacity-70">
              No accessible assessments. A verified organization membership is required.
            </p>
          )}
          {assessments.map((assessment) => (
            <article key={assessment.id} className="space-y-3 rounded-xl border p-5">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{assessment.title}</h3>
                  <p className="text-xs opacity-60">{assessment.slug} · v{assessment.version}</p>
                </div>
                <span className="text-sm font-semibold">{assessment.status}</span>
              </div>
              <p className="text-sm opacity-70">
                {assessment.questions.length} question(s) · {assessment.duration_minutes} minutes ·
                {" "}{assessment.maximum_marks} marks
              </p>
              <p className="break-all font-mono text-xs opacity-50">{assessment.id}</p>
              {assessment.status === "review_required" && (
                <button
                  type="button"
                  disabled={busy || evidence.trim().length < 10}
                  className="rounded-md border border-sky-500 px-4 py-2 text-sm disabled:opacity-40"
                  onClick={() => void publish(assessment.id)}
                >
                  Approve as independent reviewer
                </button>
              )}
              {assessment.status === "published" && (
                <button
                  type="button"
                  disabled={busy || !candidateId.trim()}
                  className="rounded-md bg-sky-600 px-4 py-2 text-sm text-white disabled:opacity-40"
                  onClick={() => void invite(assessment.id)}
                >
                  Invite registered candidate
                </button>
              )}
            </article>
          ))}
        </section>

        <aside className="space-y-6">
          <section className="rounded-2xl border p-6">
            <h2 className="mb-4 text-lg font-semibold">New draft</h2>
            <form onSubmit={(event) => void create(event)} className="space-y-4">
              <label className="block text-sm">
                Assessment title
                <input
                  required minLength={5} maxLength={160}
                  className="mt-1 w-full rounded-lg border bg-transparent p-3"
                  value={title} onChange={(event) => setTitle(event.target.value)}
                />
              </label>
              <label className="block text-sm">
                Slug
                <input
                  required minLength={3} maxLength={100}
                  pattern="[a-z0-9][a-z0-9-]{2,99}"
                  className="mt-1 w-full rounded-lg border bg-transparent p-3"
                  value={slug} onChange={(event) => setSlug(event.target.value)}
                />
              </label>
              <label className="block text-sm">
                Written problem prompt
                <textarea
                  required minLength={10} rows={5}
                  className="mt-1 w-full rounded-lg border bg-transparent p-3"
                  value={prompt} onChange={(event) => setPrompt(event.target.value)}
                />
              </label>
              <button
                disabled={busy} type="submit"
                className="rounded-lg bg-sky-600 px-4 py-2 font-semibold text-white disabled:opacity-40"
              >
                Create review-gated draft
              </button>
            </form>
          </section>
          <section className="space-y-4 rounded-2xl border p-6">
            <h2 className="font-semibold">Reviewer evidence and invitations</h2>
            <label className="block text-sm">
              Independent review receipts (rights, technical and editorial)
              <textarea
                value={evidence} minLength={10} rows={4}
                onChange={(event) => setEvidence(event.target.value)}
                className="mt-1 w-full rounded-lg border bg-transparent p-3"
              />
            </label>
            <p className="text-xs opacity-65">
              This early interface sends one receipt text across three evidence fields.
              Formal distinct reviews and reviewer assignment remain release-gated.
            </p>
            <label className="block text-sm">
              Registered candidate UUID
              <input
                value={candidateId}
                onChange={(event) => setCandidateId(event.target.value)}
                className="mt-1 w-full rounded-lg border bg-transparent p-3 font-mono text-xs"
              />
            </label>
            {invitation && (
              <div className="space-y-2 rounded-lg border border-sky-500 p-3">
                <h3 className="font-semibold">New invitation — share privately</h3>
                <p className="text-xs">ID</p>
                <p className="break-all font-mono text-xs">{invitation.id}</p>
                <p className="text-xs">One-time secret (not stored by this page)</p>
                <p className="break-all font-mono text-xs">{invitation.acceptance_secret}</p>
                <p className="text-xs opacity-70">Expires {invitation.expires_at}</p>
              </div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
