"use client";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import {
  readCandidateInvitationFragment,
  safeSignInReturnPath,
  stashPendingCandidateInvitation,
} from "@/lib/assessment-invitation-link";
import { ApiError, getProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { AppShell } from "./app-shell";

// Public routes contain only marketing or self-contained guest practice surfaces.
const publicRoutes = [
  "/",
  "/sign-in",
  "/sign-up",
  "/auth/callback",
  "/practice/code-typing",
  "/practice/typing-arcade",
];

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { principal, status } = useAuth();
  const isPublic = publicRoutes.some(
    (route) =>
      route === "/"
        ? pathname === "/"
        : pathname === route || pathname.startsWith(`${route}/`),
  );
  const isCandidate = principal?.roles.includes("candidate") ?? false;
  const isStandalonePractice = ["/practice/code-typing", "/practice/typing-arcade"].some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  const candidateRoute = [
    "/problems",
    "/questions",
    "/companies",
    "/system-design-library",
    "/question-bank",
    "/practice",
    "/workspace",
    "/learning-paths",
    "/mock-interviews",
    "/pr-review",
    "/ai-arena",
    "/attempts",
    "/assessments",
    "/employer",
    "/design-lab",
    "/progress",
    "/study-workspace",
    "/onboarding",
    "/profile",
    "/settings",
  ].some(
    (route) =>
      pathname === route || (route !== "/" && pathname.startsWith(`${route}/`)),
  );
  const wrongWorkspace =
    !isPublic && status === "authenticated" && isCandidate && !candidateRoute;
  const isEmployerAssessment =
    pathname === "/assessments" || pathname.startsWith("/assessments/");
  const isEmployerWorkflow =
    pathname === "/employer" || pathname.startsWith("/employer/");
  // An employer screening invitation must not require the candidate to
  // contribute their unrelated private learner-onboarding profile.
  const shouldCheckCandidateProfile =
    !isPublic && status === "authenticated" && isCandidate
    && !wrongWorkspace && !isEmployerAssessment && !isEmployerWorkflow;
  const candidateProfile = useQuery({
    queryKey: ["candidate-profile", "auth-gate"],
    queryFn: ({ signal }) => getProfile(signal),
    enabled: shouldCheckCandidateProfile,
    retry: false,
    staleTime: 60_000,
  });
  const profileMissing =
    candidateProfile.isError &&
    candidateProfile.error instanceof ApiError &&
    candidateProfile.error.status === 404;
  const onboardingRequired =
    shouldCheckCandidateProfile && profileMissing && pathname !== "/onboarding";

  useEffect(() => {
    if (!isPublic && status === "anonymous") {
      if (isEmployerAssessment && window.location.hash.startsWith("#invitation=")) {
        const link = readCandidateInvitationFragment(window.location.hash);
        if (link) {
          try {
            stashPendingCandidateInvitation(window.sessionStorage, link);
          } catch {
            // Browser storage may be disabled. The candidate can still enter
            // the credentials manually after authentication.
          }
        }
        window.history.replaceState(
          window.history.state, "", window.location.pathname + window.location.search,
        );
      }
      router.replace(`/sign-in?returnTo=${encodeURIComponent(pathname)}`);
      return;
    }
    if (
      (pathname === "/sign-in" || pathname === "/sign-up") &&
      status === "authenticated"
    ) {
      const requested = new URLSearchParams(window.location.search).get("returnTo");
      router.replace(safeSignInReturnPath(requested));
      return;
    }
    if (wrongWorkspace) {
      router.replace("/workspace");
      return;
    }
    if (onboardingRequired) router.replace("/onboarding");
  }, [isEmployerAssessment, isPublic, onboardingRequired, pathname, router, status, wrongWorkspace]);

  if (isPublic && !(isStandalonePractice && status === "authenticated")) return children;
  if (
    status !== "authenticated" ||
    wrongWorkspace ||
    onboardingRequired ||
    (shouldCheckCandidateProfile && candidateProfile.isLoading)
  ) {
    return (
      <div className="auth-loading">
        <LoaderCircle className="spin" size={26} />
        <strong>
          {shouldCheckCandidateProfile && candidateProfile.isLoading
            ? "Checking candidate profile"
            : "Restoring secure session"}
        </strong>
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
