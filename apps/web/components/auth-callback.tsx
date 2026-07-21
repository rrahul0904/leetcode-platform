"use client";

import { AlertTriangle, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { authReturnPath, useAuth } from "@/lib/auth";

export function AuthCallback() {
  const searchParams = useSearchParams();
  const { completeSignIn } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const exchangeStarted = useRef(false);
  const code = searchParams.get("code");
  const state = searchParams.get("state");

  useEffect(() => {
    if (exchangeStarted.current) return;
    exchangeStarted.current = true;
    if (!code || !state) {
      queueMicrotask(() =>
        setError("The authorization response is missing its code or state."),
      );
      return;
    }
    void completeSignIn(code, state)
      .then(() => window.location.replace(authReturnPath()))
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Sign-in failed."),
      );
  }, [code, completeSignIn, state]);

  return (
    <main className="callback-page">
      {error ? (
        <>
          <AlertTriangle size={26} />
          <strong>Secure sign-in could not be completed.</strong>
          <p>{error}</p>
          <Link className="button button--dark" href="/sign-in">
            Return to sign in
          </Link>
        </>
      ) : (
        <>
          <LoaderCircle className="spin" size={28} />
          <strong>Validating authorization code and restoring session</strong>
          <p>The API will independently validate the resulting token.</p>
        </>
      )}
    </main>
  );
}
