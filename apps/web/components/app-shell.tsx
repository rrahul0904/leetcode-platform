"use client";

import {
  BookOpen,
  CircleGauge,
  FileCheck2,
  FileUp,
  Link2,
  LayoutDashboard,
  Menu,
  Radar,
  Route,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { useAuth } from "@/lib/auth";

const workspaceNav = [
  ["Home", "/", LayoutDashboard],
  ["Question bank", "/question-bank", BookOpen],
  ["Workspace", "/workspace", FileCheck2],
  ["Learning paths", "/learning-paths", Route],
  ["Readiness", "/progress", CircleGauge],
] as const;

const administratorNav = [
  ["Overview", "/", LayoutDashboard],
  ["Content", "/admin/questions", BookOpen],
  ["Review queue", "/content-review", FileCheck2],
  ["Sources", "/admin/sources", Radar],
  ["Catalog status", "/admin/catalog-status", Link2],
] as const;

const authorNav = [
  ["Overview", "/", LayoutDashboard],
  ["Content", "/admin/questions", BookOpen],
  ["Generate content", "/admin/questions/new", FileUp],
] as const;

const reviewerNav = [
  ["Overview", "/", LayoutDashboard],
  ["Review queue", "/content-review", FileCheck2],
  ["Question bank", "/question-bank", BookOpen],
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/workspace" && pathname.startsWith("/practice/")) return true;
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

function labelFor(
  pathname: string,
  items: ReadonlyArray<readonly [string, string, typeof BookOpen]>,
) {
  return items.find(([, href]) => isActive(pathname, href))?.[0] ?? "Workspace";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { principal, signOut } = useAuth();
  const isAdministrator = principal?.roles.includes("platform-administrator");
  const isAuthor = principal?.roles.includes("content-author");
  const isReviewer = principal?.roles.some((role) =>
    ["technical-reviewer", "editorial-reviewer"].includes(role),
  );
  const navigation = isAdministrator
    ? administratorNav
    : isAuthor
      ? authorNav
      : isReviewer
        ? reviewerNav
        : workspaceNav;
  const isCandidateWorkspace = !isAdministrator && !isAuthor && !isReviewer;
  const currentLabel = labelFor(pathname, navigation);
  const initials =
    principal?.display_name
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() ?? "?";

  const renderNav = (
    items: ReadonlyArray<readonly [string, string, typeof BookOpen]>,
  ) =>
    items.map(([label, href, Icon]) => {
      const active = isActive(pathname, href);
      return (
        <Link
          className={`nav-item ${active ? "nav-item--active" : ""}`}
          href={href}
          key={href}
          onClick={() => setMobileNavOpen(false)}
          aria-current={active ? "page" : undefined}
        >
          <Icon size={18} />
          {label}
          {active && <span className="nav-pulse" />}
        </Link>
      );
    });

  return (
    <div
      className={`app-shell ${isCandidateWorkspace ? "app-shell--candidate" : "app-shell--management"}`}
    >
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobileNavOpen && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileNavOpen ? "sidebar--open" : ""}`}>
        <Link
          className="brand"
          href="/"
          onClick={() => setMobileNavOpen(false)}
        >
          <span className="brand__mark">R</span>
          <span>
            <strong>RIGOR</strong>
            <small>INTERVIEW SYSTEMS LAB</small>
          </span>
        </Link>
        <button
          className="mobile-close"
          type="button"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
        <nav aria-label="Primary navigation">
          <p className="nav-label">
            {isAdministrator || isAuthor || isReviewer ? "MANAGE" : "PRACTICE"}
          </p>
          {renderNav(navigation)}
        </nav>
        <div className="sidebar-note">
          <span>LOCAL WORKSPACE</span>
          <strong>
            {isAdministrator ? "Content administration" : "Interview practice"}
          </strong>
          <p>Only reviewed and published questions appear to candidates.</p>
        </div>
      </aside>

      <main id="main-content">
        <header className="topbar">
          <button
            className="mobile-menu"
            type="button"
            aria-label="Open navigation"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            <strong>{currentLabel}</strong>
          </div>
          <div className="topbar__right">
            <span className="api-status">
              <i /> Connected
            </span>
            <div className="profile-control">
              <button
                className="avatar"
                aria-label="Open profile menu"
                aria-expanded={profileOpen}
                onClick={() => setProfileOpen((open) => !open)}
              >
                {initials}
              </button>
              {profileOpen && (
                <div className="profile-menu">
                  <span>
                    {principal?.authentication_provider ?? "AUTHENTICATED"}
                  </span>
                  <strong>{principal?.display_name}</strong>
                  <p>
                    {principal?.email}
                    <br />
                    {principal?.roles.join(" · ")}
                  </p>
                  <Link href="/progress" onClick={() => setProfileOpen(false)}>
                    View readiness
                  </Link>
                  {principal?.roles.includes("candidate") && (
                    <Link
                      href="/onboarding"
                      onClick={() => setProfileOpen(false)}
                    >
                      Edit profile
                    </Link>
                  )}
                  <button
                    className="profile-sign-out"
                    onClick={() => {
                      signOut();
                      window.location.assign("/sign-in");
                    }}
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        {children}
        <footer className="site-footer">
          {isCandidateWorkspace ? (
            <>
              <span>RIGOR PLATFORM · INTERACTIVE PRACTICE</span>
              <span>API-BACKED CONTENT · ISOLATED EXECUTION</span>
            </>
          ) : (
            <>
              <span>
                Independent preparation platform. No employer affiliation.
              </span>
              <span>Content states and readiness claims are evidence-gated.</span>
            </>
          )}
        </footer>
      </main>
    </div>
  );
}
