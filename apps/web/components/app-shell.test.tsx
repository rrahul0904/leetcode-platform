import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/admin/questions" }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    principal: {
      authentication_provider: "local-oidc",
      display_name: "Parker Platform",
      email: "platform-administrator@rigor.test",
      roles: ["platform-administrator"],
    },
    signOut: vi.fn(),
  }),
}));

describe("AppShell", () => {
  it("shows a focused role-specific navigation", () => {
    render(
      <AppShell>
        <div>Content page</div>
      </AppShell>,
    );
    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(4);
    expect(
      within(navigation).getByRole("link", { name: "Content" }),
    ).toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: "Learning paths" }),
    ).not.toBeInTheDocument();
  });
});
