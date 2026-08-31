import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("candidate AppShell", () => {
  it("exposes the focused SkillsForge AI candidate navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200 }),
    );

    render(
      <AppShell>
        <div>Candidate question bank</div>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(4);
    expect(
      within(navigation).getByRole("link", { name: "Overview" }),
    ).toHaveAttribute("href", "/");
    expect(
      within(navigation).getByRole("link", { name: "CareerOS" }),
    ).toHaveAttribute("href", "/career");
    expect(
      within(navigation).getByRole("link", { name: "Question Bank" }),
    ).toHaveAttribute("href", "/question-bank");
    expect(
      within(navigation).getByRole("link", { name: "Question Bank" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      within(navigation).getByRole("link", { name: "Progress" }),
    ).toHaveAttribute("href", "/progress");
    expect(
      screen.getByRole("link", { name: "Search question bank" }),
    ).toHaveAttribute("href", "/question-bank");

    await waitFor(() =>
      expect(screen.getByTitle("SkillsForge AI API: Connected")).toBeInTheDocument(),
    );
  });
});