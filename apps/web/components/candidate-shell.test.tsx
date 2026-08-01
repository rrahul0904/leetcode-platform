import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/workspace" }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    principal: {
      authentication_provider: "local-oidc",
      display_name: "Casey Candidate",
      email: "candidate@rigor.test",
      roles: ["candidate"],
    },
    signOut: vi.fn(),
  }),
}));

describe("candidate AppShell", () => {
  it("matches the cinematic demo navigation with a real workspace route", () => {
    render(
      <AppShell>
        <div>Candidate workspace entry</div>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(5);
    expect(within(navigation).getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      within(navigation).getByRole("link", { name: "Question bank" }),
    ).toHaveAttribute("href", "/question-bank");
    expect(
      within(navigation).getByRole("link", { name: "Workspace" }),
    ).toHaveAttribute("href", "/workspace");
    expect(
      within(navigation).getByRole("link", { name: "Learning paths" }),
    ).toHaveAttribute("href", "/learning-paths");
    expect(
      within(navigation).getByRole("link", { name: "Readiness" }),
    ).toHaveAttribute("href", "/progress");
  });
});
