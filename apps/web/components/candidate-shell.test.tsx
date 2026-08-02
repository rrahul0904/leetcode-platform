import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/problems" }));
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
  it("exposes the recording-inspired candidate navigation", () => {
    render(
      <AppShell>
        <div>Candidate problem bank</div>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(7);
    expect(within(navigation).getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      within(navigation).getByRole("link", { name: "Problems" }),
    ).toHaveAttribute("href", "/problems");
    expect(
      within(navigation).getByRole("link", { name: "Companies" }),
    ).toHaveAttribute("href", "/companies");
    expect(
      within(navigation).getByRole("link", { name: "Study plans" }),
    ).toHaveAttribute("href", "/learning-paths");
    expect(
      within(navigation).getByRole("link", { name: "Mock exams" }),
    ).toHaveAttribute("href", "/mock-interviews");
    expect(
      within(navigation).getByRole("link", { name: "System design" }),
    ).toHaveAttribute("href", "/system-design-library");
    expect(
      within(navigation).getByRole("link", { name: "Readiness" }),
    ).toHaveAttribute("href", "/progress");
  });
});
