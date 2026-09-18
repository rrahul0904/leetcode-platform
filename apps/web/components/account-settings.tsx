"use client";

import { UserProfile } from "@clerk/nextjs";
import { ShieldCheck } from "lucide-react";

import { authMode } from "@/lib/auth";

export function AccountSettings() {
  if (authMode !== "clerk") {
    return (
      <div className="page-content">
        <section className="panel section-block">
          <span className="eyebrow">ACCOUNT SECURITY</span>
          <h1>Account settings are managed by the production identity provider.</h1>
          <p className="lead-copy">
            Local development identity does not expose account-management controls.
            The production SkillsForge AI deployment uses Clerk for verified email,
            connected sign-in methods, sessions, and multi-factor authentication.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="page-content page-content--wide">
      <section className="account-settings-intro">
        <span className="eyebrow">ACCOUNT & SECURITY</span>
        <h1>Manage how you sign in to SkillsForge AI.</h1>
        <p>
          Identity and authentication are managed by Clerk. SkillsForge AI keeps
          interview progress, authorization, roles, and learning evidence in the
          application database.
        </p>
        <div className="boundary-note">
          <ShieldCheck size={18} />
          <span>
            Changing an identity setting here does not grant application roles or
            permissions. Authorization remains database-controlled.
          </span>
        </div>
      </section>
      <div className="clerk-settings-shell">
        <UserProfile routing="path" path="/settings" />
      </div>
    </div>
  );
}
