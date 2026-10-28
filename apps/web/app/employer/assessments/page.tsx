"use client";

import { useEffect, useState } from "react";

import { buildCandidateInvitationLink } from "@/lib/assessment-invitation-link";

import {
  createEmployerAssessment,
  inviteEmployerCandidate,
  listAssessmentInvitations,
  revokeAssessmentInvitation,
  listEmployerAssessments,
  publishEmployerAssessment,
  savePrivateAnswerKey,
  stageEmployerCodeTestBundle,
  type EmployerAssessment,
  type EmployerInvitation,
  type EmployerInvitationStatus,
  type AssessmentQuestion,
} from "@/lib/employer-assessment-api";

type CodeFixtureDraft = {
  sampleInput: string;
  sampleExpected: string;
  hiddenInput: string;
  hiddenExpected: string;
};

function emptyFixture(): CodeFixtureDraft {
  return { sampleInput: "", sampleExpected: "", hiddenInput: "", hiddenExpected: "" };
}

export default function EmployerAssessmentsPage() {
  const [assessments, setAssessments] = useState<EmployerAssessment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([
    { number: 1, kind: "written", prompt: "", marks: 100, options: [] },
  ]);
  const [candidateId, setCandidateId] = useState("");
  const [rightsEvidence, setRightsEvidence] = useState("");
  const [technicalEvidence, setTechnicalEvidence] = useState("");
  const [editorialEvidence, setEditorialEvidence] = useState("");
  const [invitation, setInvitation] = useState<EmployerInvitation | null>(null);
  const [shownInvitations, setShownInvitations] = useState<string | null>(null);
  const [invitationStatuses, setInvitationStatuses] = useState<EmployerInvitationStatus[]>([]);
  const [privateAnswers, setPrivateAnswers] = useState<Record<string, "A" | "B" | "C" | "D">>({});
  const [privateGuidance, setPrivateGuidance] = useState("");
  const [codeFixtures, setCodeFixtures] = useState<Record<string, CodeFixtureDraft>>({});

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
        questions: questions.map((q, index) => ({
          ...q,
          number: index + 1,
          prompt: q.prompt.trim(),
          options: q.options.map((option) => option.trim()),
        })),
      });
      setNotice("Draft " + response.slug + " created. An independent reviewer must approve it.");
      setTitle("");
      setSlug("");
      setQuestions([
        { number: 1, kind: "written", prompt: "", marks: 100, options: [] },
      ]);
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
        rights_evidence: rightsEvidence.trim(),
        technical_evidence: technicalEvidence.trim(),
        editorial_evidence: editorialEvidence.trim(),
      });
      setNotice("Published after independent reviewer attestation.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot approve assessment.");
    } finally {
      setBusy(false);
    }
  }

  async function viewInvitations(id: string) {
    if (shownInvitations === id) {
      setShownInvitations(null);
      setInvitationStatuses([]);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const items = await listAssessmentInvitations(id);
      setShownInvitations(id);
      setInvitationStatuses(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot list invitations.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeInvitation(assessmentId: string, invitationId: string) {
    if (busy || !window.confirm("Revoke this pending candidate invitation?")) return;
    setBusy(true);
    setError("");
    try {
      await revokeAssessmentInvitation(invitationId);
      setInvitationStatuses(await listAssessmentInvitations(assessmentId));
      setNotice("Pending invitation revoked. Its one-use secret no longer works.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot revoke invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function savePrivateKey(assessment: EmployerAssessment) {
    if (busy || privateGuidance.trim().length < 10) return;
    const mcq = assessment.questions.filter((q) => q.kind === "multiple_choice");
    const answers: Record<number, "A" | "B" | "C" | "D"> = {};
    for (const question of mcq) {
      const choice = privateAnswers[assessment.id + ":" + question.number];
      if (!choice) {
        setError("Select a confidential answer for each multiple-choice question.");
        return;
      }
      answers[question.number] = choice;
    }
    setBusy(true);
    setError("");
    try {
      await savePrivateAnswerKey(assessment.id, answers, privateGuidance.trim());
      setPrivateGuidance("");
      setPrivateAnswers({});
      setNotice("Confidential key saved server-side and bound to this assessment version.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save confidential key.");
    } finally {
      setBusy(false);
    }
  }

  function editFixture(key: string, field: keyof CodeFixtureDraft, value: string) {
    setCodeFixtures((current) => ({
      ...current,
      [key]: { ...(current[key] ?? emptyFixture()), [field]: value },
    }));
  }

  async function saveCodeFixtures(assessment: EmployerAssessment, question: AssessmentQuestion) {
    const key = assessment.id + ":" + question.number;
    const fixture = codeFixtures[key] ?? emptyFixture();
    if (question.language !== "python" && question.language !== "sql") {
      setError("Coding question must have an explicit Python or SQL runtime.");
      return;
    }
    if (!fixture.sampleExpected.trim() || !fixture.hiddenExpected.trim()) {
      setError("Provide expected outputs for both sample and hidden test cases.");
      return;
    }
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const receipt = await stageEmployerCodeTestBundle(assessment.id, question.number, {
        language: question.language,
        cases: [
          {
            case_id: "sample_one", visibility: "sample", points: 0,
            input_data: fixture.sampleInput, expected_output: fixture.sampleExpected,
          },
          {
            case_id: "hidden_one", visibility: "hidden", points: question.marks,
            input_data: fixture.hiddenInput, expected_output: fixture.hiddenExpected,
          },
        ],
      });
      setCodeFixtures((current) => {
        const remaining = { ...current };
        delete remaining[key];
        return remaining;
      });
      setNotice(
        "Private fixture saved with version digest " + receipt.bundle_sha256.slice(0, 12)
        + ". Secure execution and grading are not connected yet.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not stage private fixtures.");
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
      setNotice("One-use invitation created. Share its secure link privately; it will not be available again after leaving this page.");
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
            Compose original multi-question assessments using coding prompts, written
            scenarios and single-answer MCQs. Execution sandboxes and secret test cases
            are gated until separately verified.
          </p>
          <a href="/employer/reviews" className="inline-block text-sm underline">
            Open submitted attempts and human scorecards
          </a>
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
              {assessment.status === "published" && (
                <div className="space-y-3 rounded-xl border p-4">
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-lg border px-4 py-2 text-sm disabled:opacity-40"
                    onClick={() => void viewInvitations(assessment.id)}
                  >
                    {shownInvitations === assessment.id ? "Hide invitations" : "View invitations"}
                  </button>
                  {shownInvitations === assessment.id && (
                    <div className="space-y-2">
                      {invitationStatuses.length === 0 && (
                        <p className="text-sm opacity-70">No invitations for this assessment.</p>
                      )}
                      {invitationStatuses.map((item) => (
                        <div key={item.id} className="rounded-lg border p-3 text-sm">
                          <p className="font-semibold">State: {item.state}</p>
                          <p className="break-all font-mono text-xs">{item.candidate_id}</p>
                          <p className="text-xs opacity-70">Expires: {item.expires_at}</p>
                          {item.state === "pending" && (
                            <button
                              type="button"
                              className="mt-2 rounded border px-3 py-1 text-xs"
                              disabled={busy}
                              onClick={() => void revokeInvitation(assessment.id, item.id)}
                            >
                              Revoke pending invitation
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {assessment.status === "review_required" && assessment.questions.some(
                (question) => question.kind === "multiple_choice" || question.kind === "code"
              ) && (
                <fieldset className="space-y-3 rounded-lg border p-4">
                  <legend className="px-2 text-sm font-semibold">
                    Restricted assessment rubric — authorized authors only
                  </legend>
                  <p className="text-xs opacity-70">
                    Key answers are sent to the restricted server-only rubric table.
                    Never paste interviewer solutions into the public question prompt.
                  </p>
                  {assessment.questions.filter((question) =>
                    question.kind === "multiple_choice"
                  ).map((question) => (
                    <label key={question.number} className="block text-sm">
                      Question {question.number} correct choice
                      <select
                        value={privateAnswers[assessment.id + ":" + question.number] ?? ""}
                        onChange={(event) => setPrivateAnswers((current) => ({
                          ...current,
                          [assessment.id + ":" + question.number]:
                            event.target.value as "A" | "B" | "C" | "D",
                        }))}
                        className="mt-2 w-full rounded-lg border bg-transparent p-2"
                      >
                        <option value="" disabled>Select correct choice</option>
                        {(["A", "B", "C", "D"] as const).map((choice) => (
                          <option key={choice} value={choice}>{choice}</option>
                        ))}
                      </select>
                    </label>
                  ))}
                  <label className="block text-sm">
                    Confidential reviewer guidance
                    <textarea
                      value={privateGuidance}
                      maxLength={20000}
                      rows={3}
                      onChange={(event) => setPrivateGuidance(event.target.value)}
                      className="mt-2 w-full rounded-lg border bg-transparent p-3"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy || privateGuidance.trim().length < 10}
                    onClick={() => void savePrivateKey(assessment)}
                    className="rounded-lg border border-sky-500 px-4 py-2 text-sm disabled:opacity-40"
                  >
                    Save restricted rubric
                  </button>
                </fieldset>
              )}
              {assessment.status === "review_required" && assessment.questions.some(
                (question) => question.kind === "code"
              ) && (
                <section className="space-y-3 rounded-lg border p-4">
                  <h4 className="text-sm font-semibold">Confidential coding test bundles</h4>
                  <p className="text-xs opacity-70">
                    Save the restricted rubric first, then stage an original sample and hidden
                    test case for every coding question. Hidden cases remain server-side.
                    This does not enable Run or automated grading until the isolated runner is certified.
                  </p>
                  {assessment.questions.filter((question) => question.kind === "code").map(
                    (question) => {
                      const key = assessment.id + ":" + question.number;
                      const values = codeFixtures[key] ?? emptyFixture();
                      return (
                        <fieldset key={key} className="space-y-3 rounded-lg border p-3">
                          <legend className="px-1 text-sm font-semibold">
                            Question {question.number} · {question.language?.toUpperCase()}
                          </legend>
                          {([
                            ["sampleInput", "Sample input", values.sampleInput],
                            ["sampleExpected", "Expected sample output", values.sampleExpected],
                            ["hiddenInput", "Confidential hidden input", values.hiddenInput],
                            ["hiddenExpected", "Expected hidden output", values.hiddenExpected],
                          ] as const).map(([field, label, value]) => (
                            <label key={field} className="block text-sm">
                              {label}
                              <textarea
                                aria-label={`Question ${question.number} ${label}`}
                                value={value}
                                rows={3}
                                maxLength={20000}
                                spellCheck={false}
                                onChange={(event) => editFixture(
                                  key, field, event.target.value,
                                )}
                                className="mt-1 w-full rounded-lg border bg-transparent p-2 font-mono text-xs"
                              />
                            </label>
                          ))}
                          <button
                            type="button"
                            disabled={busy || !values.sampleExpected.trim()
                              || !values.hiddenExpected.trim()}
                            onClick={() => void saveCodeFixtures(assessment, question)}
                            className="rounded-lg border border-sky-500 px-3 py-2 text-sm disabled:opacity-40"
                          >
                            Save private sample + hidden cases
                          </button>
                        </fieldset>
                      );
                    }
                  )}
                </section>
              )}
              {assessment.status === "review_required" && (
                <button
                  type="button"
                  disabled={
                    busy || rightsEvidence.trim().length < 10
                    || technicalEvidence.trim().length < 10
                    || editorialEvidence.trim().length < 10
                  }
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
              <fieldset className="space-y-5 rounded-lg border p-3">
                <legend className="px-2 font-semibold">Questions and marks</legend>
                {questions.map((question, index) => (
                  <div key={question.number} className="space-y-3 rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <strong className="text-sm">Question {index + 1}</strong>
                      <button
                        type="button"
                        disabled={questions.length === 1}
                        className="rounded border px-2 py-1 text-xs disabled:opacity-40"
                        onClick={() => setQuestions((all) =>
                          all.filter((_, i) => i !== index).map((q, i) => ({
                            ...q, number: i + 1,
                          }))
                        )}
                      >
                        Remove
                      </button>
                    </div>
                    <label className="block text-sm">
                      Type
                      <select
                        value={question.kind}
                        className="mt-1 w-full rounded-lg border bg-transparent p-2"
                        onChange={(event) => {
                          const kind = event.target.value as AssessmentQuestion["kind"];
                          setQuestions((all) => all.map((q, i) => (
                            i === index ? {
                              ...q, kind,
                              language: kind === "code" ? "python" : null,
                              options: kind === "multiple_choice" ? ["", "", "", ""] : [],
                            } : q
                          )));
                        }}
                      >
                        <option value="written">Written scenario</option>
                        <option value="code">Coding (review-only until runner available)</option>
                        <option value="multiple_choice">Multiple choice</option>
                      </select>
                    </label>
                    {question.kind === "code" && (
                      <label className="block text-sm">
                        Coding language
                        <select
                          aria-label={`Question ${question.number} coding language`}
                          value={question.language ?? "python"}
                          className="mt-1 w-full rounded-lg border bg-transparent p-2"
                          onChange={(event) => setQuestions((all) => all.map((q, i) =>
                            i === index ? { ...q, language: event.target.value as "python" | "sql" } : q
                          ))}
                        >
                          <option value="python">Python</option>
                          <option value="sql">SQL</option>
                        </select>
                      </label>
                    )}
                    <label className="block text-sm">
                      Points
                      <input
                        type="number" required min={1} max={100}
                        className="mt-1 w-full rounded-lg border bg-transparent p-2"
                        value={question.marks}
                        onChange={(event) => {
                          const marks = Number(event.target.value);
                          setQuestions((all) => all.map((q, i) =>
                            i === index ? { ...q, marks } : q
                          ));
                        }}
                      />
                    </label>
                    <label className="block text-sm">
                      Public question prompt
                      <textarea
                        required minLength={10} maxLength={20000} rows={4}
                        className="mt-1 w-full rounded-lg border bg-transparent p-3"
                        value={question.prompt}
                        onChange={(event) => setQuestions((all) => all.map((q, i) =>
                          i === index ? { ...q, prompt: event.target.value } : q
                        ))}
                      />
                    </label>
                    {question.kind === "multiple_choice" && (
                      <div className="space-y-2">
                        <p className="text-xs opacity-65">
                          Enter four public options. Correct answers are not stored in this builder.
                        </p>
                        {question.options.map((option, choice) => (
                          <label key={choice} className="block text-sm">
                            Option {String.fromCharCode(65 + choice)}
                            <input
                              required maxLength={2000}
                              value={option}
                              className="mt-1 w-full rounded-lg border bg-transparent p-2"
                              onChange={(event) => setQuestions((all) => all.map((q, i) =>
                                i === index ? {
                                  ...q,
                                  options: q.options.map((o, j) =>
                                    j === choice ? event.target.value : o
                                  ),
                                } : q
                              ))}
                            />
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  disabled={questions.length >= 100}
                  onClick={() => setQuestions((all) => [...all, {
                    number: all.length + 1,
                    kind: "written",
                    prompt: "",
                    marks: 10,
                    options: [],
                  }])}
                  className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
                >
                  Add question
                </button>
                <p className="text-sm opacity-70">
                  Total points: {questions.reduce((sum, q) => sum + q.marks, 0)}
                </p>
              </fieldset>
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
            {([
              ["Rights and originality evidence", rightsEvidence, setRightsEvidence],
              ["Technical correctness review", technicalEvidence, setTechnicalEvidence],
              ["Editorial and accessibility review", editorialEvidence, setEditorialEvidence],
            ] as const).map(([label, value, onChange]) => (
              <label key={label} className="block text-sm">
                {label}
                <textarea
                  value={value} required minLength={10} maxLength={500} rows={3}
                  onChange={(event) => onChange(event.target.value)}
                  className="mt-1 w-full rounded-lg border bg-transparent p-3"
                />
              </label>
            ))}
            <p className="text-xs opacity-65">
              Review evidence is attributed to the independently authenticated approver.
              Formal multi-person review queues remain a release gate.
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
                <button
                  type="button"
                  className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  onClick={() => {
                    try {
                      const link = buildCandidateInvitationLink(window.location.origin, {
                        invitationId: invitation.id,
                        acceptanceSecret: invitation.acceptance_secret,
                      });
                      void navigator.clipboard.writeText(link).then(
                        () => setNotice("One-use HTTPS invitation link copied. Share only with the intended registered candidate."),
                        () => setError("Clipboard permission denied. Copy the ID and secret privately instead."),
                      );
                    } catch {
                      setError("The application is not on an approved HTTPS origin. Copy the ID and secret privately instead.");
                    }
                  }}
                >
                  Copy secure invitation link
                </button>
                <p className="text-xs opacity-70">
                  The credential stays in the URL fragment, not in the web request.
                  Do not paste this link in public messages or analytics tools.
                </p>
                <p className="text-xs opacity-70">Expires {invitation.expires_at}</p>
              </div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
