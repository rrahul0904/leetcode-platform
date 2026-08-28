import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthGate } from "@/components/auth-gate";
import { QueryProvider } from "@/components/query-provider";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";
import "./cinematic.css";
import "./cinematic-catalog.css";
import "./cinematic-support.css";
import "./cinematic-workflows.css";
import "./knowledge-bank.css";
import "./knowledge-collections.css";
import "./question-bank-operations.css";
import "./coding-pad.css";
import "./controlled-code-editor.css";
import "./attempt-history.css";
import "./certification-experience.css";
import "./curriculum-experience.css";
import "./editorial-experience.css";

export const metadata: Metadata = {
  title: "SkillsForge AI — Technical Interview Platform",
  description:
    "AI-powered technical interview preparation with persistent practice, secure code execution, evidence-driven progress, and role-focused learning paths.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const application = (
    <QueryProvider>
      <AuthProvider>
        <AuthGate>{children}</AuthGate>
      </AuthProvider>
    </QueryProvider>
  );
  const clerkEnabled = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "clerk";

  return (
    <html lang="en">
      <body>{clerkEnabled ? <ClerkProvider>{application}</ClerkProvider> : application}</body>
    </html>
  );
}
