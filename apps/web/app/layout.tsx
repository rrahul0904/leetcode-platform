import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthGate } from "@/components/auth-gate";
import { QueryProvider } from "@/components/query-provider";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";
import "./cinematic.css";

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
