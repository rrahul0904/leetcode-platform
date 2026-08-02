import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/journal" }));
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
  it("exposes the recording-grade horizontal candidate navigation", () => {
    render(
      <AppShell>
        <div>Candidate journal</div>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(8);
    expect(within(navigation).getByRole("link", { name: "Learn" })).toHaveAttribute(
      "href",
      "/learning-paths",
    );
    expect(
      within(navigation).getByRole("link", { name: "Problems" }),
    ).toHaveAttribute("href", "/problems");
    expect(
      within(navigation).getByRole("link", { name: "Companies" }),
    ).toHaveAttribute("href", "/companies");
    expect(
      within(navigation).getByRole("link", { name: "Mock exams" }),
    ).toHaveAttribute("href", "/mock-interviews");
    expect(
      within(navigation).getByRole("link", { name: "System design" }),
    ).toHaveAttribute("href", "/system-design-library");
    expect(within(navigation).getByRole("link", { name: "Journal" })).toHaveAttribute(
      "href",
      "/journal",
    );
    expect(within(navigation).getByRole("link", { name: "Journal" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(navigation).getByRole("link", { name: "Resources" }),
    ).toHaveAttribute("href", "/resources");
    expect(
      within(navigation).getByRole("link", { name: "Readiness" }),
    ).toHaveAttribute("href", "/progress");
    expect(screen.getByRole("link", { name: "Search problems" })).toHaveAttribute(
      "href",
      "/problems",
    );
  });
});
