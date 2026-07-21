"use client";

import {
  ArrowRight,
  BookOpenCheck,
  FilePenLine,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth";

const primaryIdentities = [
  [
    "candidate",
    "Practice as a candidate",
    "Browse questions and follow a learning plan.",
    BookOpenCheck,
  ],
  [
    "platform-administrator",
    "Manage content",
    "Create, review, and publish the question library.",
    ShieldCheck,
  ],
] as const;

const specialistIdentities = [
  [
    "author",
    "Content author",
    "Create and revise question drafts.",
    FilePenLine,
  ],
  [
    "technical-reviewer",
    "Technical reviewer",
    "Review correctness and technical depth.",
    UserCheck,
  ],
  [
    "editorial-reviewer",
    "Editorial reviewer",
    "Review clarity, originality, and fairness.",
    Users,
  ],
] as const;

export function SignIn() {
  const { signIn } = useAuth();
  const searchParams = useSearchParams();
  const [pending, setPending] = useState<string | null>(null);
  const returnTo = searchParams.get("returnTo") ?? "/";

  async function begin(identity: string) {
    setPending(identity);
    try {
      await signIn(identity, returnTo);
    } catch {
      setPending(null);
    }
  }

  return (
    <main className="sign-in-page">
      <section className="sign-in-brand">
        <div className="brand__mark">R</div>
        <span>RIGOR INTERVIEW SYSTEMS LAB</span>
        <h1>Practice interviews or manage content.</h1>
        <p>Choose a local workspace to preview the application.</p>
        <div className="sign-in-security">
          <ShieldCheck size={18} />
          <span>
            <strong>Secure local sign-in</strong>
            <small>Each workspace uses its real API permissions.</small>
          </span>
        </div>
      </section>
      <section className="identity-picker">
        <span className="eyebrow">CHOOSE A WORKSPACE</span>
        <h2>What would you like to do?</h2>
        <div className="identity-list">
          {primaryIdentities.map(([key, label, description, Icon]) => (
            <button
              key={key}
              disabled={pending !== null}
              onClick={() => void begin(key)}
            >
              <Icon size={18} />
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
              {pending === key ? <i>Opening…</i> : <ArrowRight size={16} />}
            </button>
          ))}
        </div>
        <details className="specialist-roles">
          <summary>Open a specialist review role</summary>
          <div className="identity-list">
            {specialistIdentities.map(([key, label, description, Icon]) => (
              <button
                key={key}
                disabled={pending !== null}
                onClick={() => void begin(key)}
              >
                <Icon size={18} />
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
                {pending === key ? <i>Opening…</i> : <ArrowRight size={16} />}
              </button>
            ))}
          </div>
        </details>
        <small className="local-only-note">Local preview roles only.</small>
      </section>
    </main>
  );
}
