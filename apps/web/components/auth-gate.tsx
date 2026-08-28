"use client";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { ApiError, getProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { AppShell } from "./app-shell";

const publicRoutes = ["/sign-in", "/sign-up", "/auth/callback"];

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { principal, status } = useAuth();
  const isPublic = publicRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  const isCandidate = principal?.roles.includes("candidate") ?? false;
  const candidateRoute = [
    "/",
    "/problems",
    "/questions",
    "/companies",
    "/system-design-library",
    "/question-bank",
    "/practice",
    "/workspace",
    "/learning-paths",
    "/mock-interviews",
    "/progress",
    "/onboarding",
    "/profile",
    "/settings",
  ].some(
    (route) =>
      pathname === route || (route !== "/" && pathname.startsWith(`${route}/`)),
  );
  const wrongWorkspace =
    !isPublic && status === "authenticated" && isCandidate && !candidateRoute;
  const shouldCheckCandidateProfile =
    !isPublic && status === "authenticated" && isCandidate && !wrongWorkspace;
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
      router.replace(`/sign-in?returnTo=${encodeURIComponent(pathname)}`);
      return;
    }
    if (
      (pathname === "/sign-in" || pathname === "/sign-up") &&
      status === "authenticated"
    ) {
      router.replace("/");
      return;
    }
    if (wrongWorkspace) {
      router.replace("/");
      return;
    }
    if (onboardingRequired) router.replace("/onboarding");
  }, [isPublic, onboardingRequired, pathname, router, status, wrongWorkspace]);

  if (isPublic) return children;
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
