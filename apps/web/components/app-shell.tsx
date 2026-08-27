"use client";

import {
  BookOpen,
  CircleGauge,
  FileCheck2,
  FileUp,
  LayoutDashboard,
  Link2,
  Menu,
  Radar,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

const candidateNav = [
  ["Overview", "/", LayoutDashboard],
  ["Question Bank", "/question-bank", BookOpen],
  ["Progress", "/progress", CircleGauge],
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

type NavigationItem = readonly [string, string, typeof BookOpen];
type ConnectionState = "checking" | "connected" | "degraded" | "offline";

function isActive(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

function labelFor(pathname: string, items: ReadonlyArray<NavigationItem>) {
  return items.find(([, href]) => isActive(pathname, href))?.[0] ?? "Workspace";
}

function connectionLabel(state: ConnectionState) {
  switch (state) {
    case "connected":
      return "Connected";
    case "degraded":
      return "Degraded";
    case "offline":
      return "Offline";
    default:
      return "Checking";
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");
  const { principal, signOut } = useAuth();
  const isAdministrator = principal?.roles.includes("platform-administrator");
  const isAuthor = principal?.roles.includes("content-author");
  const isReviewer = principal?.roles.some((role) =>
    ["technical-reviewer", "editorial-reviewer"].includes(role),
  );
  const isCandidateWorkspace = !isAdministrator && !isAuthor && !isReviewer;
  const managementNavigation: ReadonlyArray<NavigationItem> = isAdministrator
    ? administratorNav
    : isAuthor
      ? authorNav
      : reviewerNav;
  const currentLabel = labelFor(pathname, managementNavigation);
  const initials =
    principal?.display_name
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() ?? "?";

  useEffect(() => {
    let active = true;

    async function checkApi() {
      try {
        const response = await fetch("/api/backend/livez", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (!active) return;
        setConnectionState(
          response.ok ? "connected" : response.status >= 500 ? "degraded" : "offline",
        );
      } catch {
        if (active) setConnectionState("offline");
      }
    }

    void checkApi();
    const interval = window.setInterval(() => void checkApi(), 30_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  function profileMenu() {
    return (
      <div className="profile-control">
        <button
          className="avatar"
          aria-label="Open profile menu"
          aria-expanded={profileOpen}
          onClick={() => setProfileOpen((open) => !open)}
          type="button"
        >
          {initials}
        </button>
        {profileOpen && (
          <div className="profile-menu">
            <span>{principal?.authentication_provider ?? "AUTHENTICATED"}</span>
            <strong>{principal?.display_name}</strong>
            <p>
              {principal?.email}
              <br />
              {principal?.roles.join(" · ")}
            </p>
            <Link href="/progress" onClick={() => setProfileOpen(false)}>
              View progress
            </Link>
            {principal?.roles.includes("candidate") && (
              <Link href="/onboarding" onClick={() => setProfileOpen(false)}>
                Edit profile
              </Link>
            )}
            <button
              className="profile-sign-out"
              onClick={() => {
                signOut();
                window.location.assign("/sign-in");
              }}
              type="button"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    );
  }

  if (isCandidateWorkspace) {
    return (
      <div className="candidate-shell">
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        {mobileNavOpen && (
          <button
            className="candidate-nav-scrim"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
            type="button"
          />
        )}
        <header className="candidate-global-header">
          <Link className="candidate-brand" href="/">
            <span>S</span>
            <strong>SKILLFORGE</strong>
          </Link>
          <nav
            aria-label="Primary navigation"
            className={mobileNavOpen ? "candidate-global-nav is-open" : "candidate-global-nav"}
          >
            <div className="candidate-global-nav__mobile-heading">
              <span>EXPLORE SKILLFORGE</span>
              <button
                aria-label="Close navigation"
                onClick={() => setMobileNavOpen(false)}
                type="button"
              >
                <X size={18} />
              </button>
            </div>
            {candidateNav.map(([label, href, Icon]) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={active ? "is-active" : ""}
                  href={href}
                  key={href}
                  onClick={() => setMobileNavOpen(false)}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="candidate-global-controls">
            <Link
              aria-label="Search question bank"
              href="/question-bank"
              title="Search question bank"
            >
              <Search size={16} />
            </Link>
            <span
              className={`candidate-connection candidate-connection--${connectionState}`}
              title={`SkillForge API: ${connectionLabel(connectionState)}`}
            >
              <i /> {connectionLabel(connectionState)}
            </span>
            {profileMenu()}
            <button
              aria-label="Open navigation"
              className="candidate-menu-button"
              onClick={() => setMobileNavOpen(true)}
              type="button"
            >
              <Menu size={19} />
            </button>
          </div>
        </header>
        <main id="main-content" className="candidate-content">
          {children}
          <footer className="candidate-footer">
            <span>SKILLFORGE · TECHNICAL INTERVIEW PREPARATION</span>
            <span>DATABASE-BACKED CONTENT · EVIDENCE-DRIVEN PROGRESS</span>
          </footer>
        </main>
      </div>
    );
  }

  const renderManagementNav = (items: ReadonlyArray<NavigationItem>) =>
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
    <div className="app-shell app-shell--management">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobileNavOpen && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        />
      )}
      <aside className={`sidebar ${mobileNavOpen ? "sidebar--open" : ""}`}>
        <Link className="brand" href="/" onClick={() => setMobileNavOpen(false)}>
          <span className="brand__mark">R</span>
          <span>
            <strong>RIGOR</strong>
            <small>SKILLFORGE PLATFORM ADMIN</small>
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
          <p className="nav-label">MANAGE</p>
          {renderManagementNav(managementNavigation)}
        </nav>
        <div className="sidebar-note">
          <span>RIGOR GOVERNANCE ENGINE</span>
          <strong>{isAdministrator ? "Content administration" : "Governed review"}</strong>
          <p>Imported sources remain connected to canonical problems and governed review.</p>
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
            <span
              className={`api-status api-status--${connectionState}`}
              title={`Rigor API: ${connectionLabel(connectionState)}`}
            >
              <i /> {connectionLabel(connectionState)}
            </span>
            {profileMenu()}
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <span>Rigor · SkillForge platform governance and administration.</span>
          <span>Content states and readiness claims are evidence-gated.</span>
        </footer>
      </main>
    </div>
  );
}
