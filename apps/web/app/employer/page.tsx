"use client";

import { useCallback, useEffect, useState } from "react";

import {
  addEmployerMember,
  createEmployerOrganization,
  listEmployerMembers,
  listEmployerOrganizations,
  selectEmployerOrganization,
  selectedEmployerOrganization,
  type EmployerMember,
  type EmployerOrganization,
} from "@/lib/employer-assessment-api";

const roles = ["admin", "recruiter", "interviewer", "reviewer"] as const;
type MemberRole = (typeof roles)[number];

export default function EmployerWorkspacePage() {
  const [organizations, setOrganizations] = useState<EmployerOrganization[]>([]);
  const [selected, setSelected] = useState("");
  const [members, setMembers] = useState<EmployerMember[]>([]);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [userId, setUserId] = useState("");
  const [memberRole, setMemberRole] = useState<MemberRole>("reviewer");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const result = await listEmployerOrganizations();
    setOrganizations(result);
    const saved = selectedEmployerOrganization();
    const valid = result.some((item) => item.id === saved);
    setSelected(valid && saved ? saved : "");
    if (!valid) setMembers([]);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listEmployerOrganizations()
      .then((result) => {
        if (cancelled) return;
        setOrganizations(result);
        const saved = selectedEmployerOrganization();
        if (saved && result.some((item) => item.id === saved)) setSelected(saved);
      })
      .catch((cause) => {
        if (!cancelled) setError(
          cause instanceof Error ? cause.message : "Cannot load employer workspaces",
        );
      });
    return () => { cancelled = true; };
  }, []);

  const chosen = organizations.find((org) => org.id === selected);

  useEffect(() => {
    if (!selected || !chosen || !["owner", "admin"].includes(chosen.membership_role)) {
      return;
    }
    let cancelled = false;
    void listEmployerMembers(selected)
      .then((result) => { if (!cancelled) setMembers(result); })
      .catch((cause) => {
        if (!cancelled) setError(
          cause instanceof Error ? cause.message : "Cannot list members",
        );
      });
    return () => { cancelled = true; };
  }, [selected, chosen]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await createEmployerOrganization(newName.trim(), newSlug.trim());
      selectEmployerOrganization(created.id);
      setSelected(created.id);
      setNewName("");
      setNewSlug("");
      await refresh();
      setNotice("Organization created. This account is its owner.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Creation failed");
    } finally {
      setBusy(false);
    }
  }

  async function addMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      await addEmployerMember(selected, userId.trim(), memberRole);
      const result = await listEmployerMembers(selected);
      setMembers(result);
      setUserId("");
      setNotice("Member enrolled with the selected organization role.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Member enrollment failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-wider text-sky-500">
          SkillForge / Rigor · Employer workspace
        </p>
        <h1 className="text-3xl font-semibold">Your hiring organization</h1>
        <p className="max-w-3xl text-sm opacity-70">
          Create a company workspace, select it explicitly, and add registered
          colleagues as recruiters, interviewers or independent reviewers.
          Every selected workspace is checked against your live database membership.
        </p>
      </header>

      {error && <p role="alert" className="rounded-xl border border-red-500 p-3">{error}</p>}
      {notice && <p role="status" className="rounded-xl border border-sky-500 p-3">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4 rounded-2xl border p-6">
          <h2 className="text-xl font-semibold">Choose your organization</h2>
          {organizations.length === 0 && (
            <p className="text-sm opacity-70">No company workspace yet. Create one below.</p>
          )}
          {organizations.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-4 rounded-xl border p-4">
              <div>
                <h3 className="font-semibold">{item.name}</h3>
                <p className="text-sm opacity-60">
                  {item.slug} · {item.membership_role}
                </p>
              </div>
              <button
                type="button"
                aria-pressed={selected === item.id}
                onClick={() => {
                  selectEmployerOrganization(item.id);
                  setSelected(item.id);
                  setMembers([]);
                  setError("");
                  setNotice(item.name + " selected.");
                }}
                className="rounded-lg border border-sky-500 px-4 py-2 text-sm"
              >
                {selected === item.id ? "Selected" : "Use workspace"}
              </button>
            </div>
          ))}
          {chosen && (
            <div className="flex flex-wrap gap-3 pt-3">
              <a href="/employer/dashboard" className="rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white">
                Open command center
              </a>
              <a href="/employer/assessments" className="rounded-lg bg-sky-600 px-4 py-3 text-sm font-semibold text-white">
                Build assessments
              </a>
              <a href="/employer/reviews" className="rounded-lg border px-4 py-3 text-sm">
                Review candidates
              </a>
            </div>
          )}
        </section>

        <section className="rounded-2xl border p-6">
          <h2 className="mb-5 text-xl font-semibold">Create employer workspace</h2>
          <form onSubmit={(event) => void create(event)} className="space-y-4">
            <label className="block text-sm font-medium">
              Legal or company display name
              <input
                value={newName} onChange={(event) => setNewName(event.target.value)}
                required minLength={3} maxLength={160}
                className="mt-2 w-full rounded-lg border bg-transparent p-3"
              />
            </label>
            <label className="block text-sm font-medium">
              Workspace slug
              <input
                value={newSlug} onChange={(event) => setNewSlug(event.target.value)}
                required pattern="[a-z0-9][a-z0-9-]{2,99}"
                className="mt-2 w-full rounded-lg border bg-transparent p-3"
                placeholder="engineering-team"
              />
            </label>
            <button disabled={busy} type="submit" className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white disabled:opacity-40">
              Create organization
            </button>
          </form>
        </section>
      </div>

      {chosen && ["owner", "admin"].includes(chosen.membership_role) && (
        <section className="grid gap-6 rounded-2xl border p-6 lg:grid-cols-2">
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Team permissions</h2>
            <p className="text-sm opacity-70">
              Only organization owners and admins can add registered team members.
              Reviewers cannot approve their own authored assessment.
            </p>
            <ul className="space-y-2">
              {members.map((member) => (
                <li key={member.user_id} className="rounded-lg border p-3">
                  <p className="font-mono text-xs">{member.user_id}</p>
                  <p className="mt-1 text-sm">{member.role} · {member.status}</p>
                </li>
              ))}
            </ul>
          </div>
          <form onSubmit={(event) => void addMember(event)} className="space-y-4">
            <h3 className="font-semibold">Add a registered colleague</h3>
            <label className="block text-sm font-medium">
              Colleague user UUID
              <input
                value={userId} onChange={(event) => setUserId(event.target.value)}
                required className="mt-2 w-full rounded-lg border bg-transparent p-3 font-mono text-sm"
              />
            </label>
            <label className="block text-sm font-medium">
              Organization role
              <select
                value={memberRole}
                onChange={(event) => setMemberRole(event.target.value as MemberRole)}
                className="mt-2 w-full rounded-lg border bg-transparent p-3"
              >
                {roles.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            <button
              disabled={busy}
              type="submit"
              className="rounded-lg border border-sky-500 px-5 py-3 font-semibold disabled:opacity-40"
            >
              Enroll colleague
            </button>
            <p className="text-xs opacity-60">
              This initial onboarding flow accepts existing registered users by UUID.
              Email-based invitations are not implemented yet.
            </p>
          </form>
        </section>
      )}
    </main>
  );
}
