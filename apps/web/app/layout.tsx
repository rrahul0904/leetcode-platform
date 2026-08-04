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
import "./certification-experience.css";
import "./curriculum-experience.css";
import "./editorial-experience.css";

export const metadata: Metadata = {
  title: "Rigor — Interview Systems Lab",
  description:
    "Independent, evidence-driven technical interview preparation for senior through principal engineers.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <AuthProvider>
            <AuthGate>{children}</AuthGate>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
