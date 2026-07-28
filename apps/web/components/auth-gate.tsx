"use client";

import { LoaderCircle } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { useAuth } from "@/lib/auth";

import { AppShell } from "./app-shell";

const publicRoutes = ["/sign-in", "/auth/callback"];

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
    "/question-bank",
    "/practice",
    "/learning-paths",
    "/mock-interviews",
    "/progress",
    "/onboarding",
  ].some(
    (route) =>
      pathname === route || (route !== "/" && pathname.startsWith(`${route}/`)),
  );
  const wrongWorkspace =
    !isPublic && status === "authenticated" && isCandidate && !candidateRoute;

  useEffect(() => {
    if (!isPublic && status === "anonymous")
      router.replace(`/sign-in?returnTo=${encodeURIComponent(pathname)}`);
    if (pathname === "/sign-in" && status === "authenticated")
      router.replace("/");
    if (wrongWorkspace) router.replace("/");
  }, [isPublic, pathname, router, status, wrongWorkspace]);

  if (isPublic) return children;
  if (status !== "authenticated" || wrongWorkspace)
    return (
      <div className="auth-loading">
        <LoaderCircle className="spin" size={26} />
        <strong>Restoring secure session</strong>
      </div>
    );
  return <AppShell>{children}</AppShell>;
}
