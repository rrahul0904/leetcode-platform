"use client";

import {
  BookOpen,
  Building2,
  CircleGauge,
  FileCheck2,
  FileUp,
  Files,
  LayoutDashboard,
  Link2,
  Menu,
  Newspaper,
  Radar,
  Route,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { useAuth } from "@/lib/auth";

const candidateNav = [
  ["Learn", "/learning-paths", Route],
  ["Problems", "/problems", BookOpen],
  ["Companies", "/companies", Building2],
  ["Mock exams", "/mock-interviews", FileCheck2],
  ["System design", "/system-design-library", Radar],
  ["Journal", "/journal", Newspaper],
  ["Resources", "/resources", Files],
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

type NavigationItem = readonly [string, string, typeof BookOpen];

function isActive(pathname: string, href: string) {
  if (href === "/problems" && pathname.startsWith("/practice/")) return true;
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

function labelFor(pathname: string, items: ReadonlyArray<NavigationItem>) {
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
              View readiness
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
            <span>R</span>
            <strong>RIGOR</strong>
          </Link>
          <nav
            aria-label="Primary navigation"
            className={mobileNavOpen ? "candidate-global-nav is-open" : "candidate-global-nav"}
          >
            <div className="candidate-global-nav__mobile-heading">
              <span>EXPLORE RIGOR</span>
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
            <Link aria-label="Search problems" href="/problems" title="Search problems">
              <Search size={16} />
            </Link>
            <span className="candidate-connection" title="API connected">
              <i /> Live
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
            <span>RIGOR · INTERVIEW SYSTEMS LAB</span>
            <span>DATABASE-BACKED CONTENT · ISOLATED EXECUTION</span>
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
          <p className="nav-label">MANAGE</p>
          {renderManagementNav(managementNavigation)}
        </nav>
        <div className="sidebar-note">
          <span>RIGOR KNOWLEDGE BANK</span>
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
            <span className="api-status">
              <i /> Connected
            </span>
            {profileMenu()}
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <span>Independent preparation platform. No employer affiliation.</span>
          <span>Content states and readiness claims are evidence-gated.</span>
        </footer>
      </main>
    </div>
  );
}
