import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/question-bank" }));
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
  it("exposes the focused SkillForge candidate navigation", () => {
    render(
      <AppShell>
        <div>Candidate question bank</div>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(3);
    expect(within(navigation).getByRole("link", { name: "Overview" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      within(navigation).getByRole("link", { name: "Question Bank" }),
    ).toHaveAttribute("href", "/question-bank");
    expect(
      within(navigation).getByRole("link", { name: "Question Bank" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(navigation).getByRole("link", { name: "Progress" })).toHaveAttribute(
      "href",
      "/progress",
    );
    expect(screen.getByRole("link", { name: "Search question bank" })).toHaveAttribute(
      "href",
      "/question-bank",
    );
  });
});
