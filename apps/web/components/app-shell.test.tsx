import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AppShell", () => {
  it("shows a focused role-specific navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200 }),
    );

    render(
      <AppShell>
        <div>Content page</div>
      </AppShell>,
    );
    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getAllByRole("link")).toHaveLength(5);
    expect(
      within(navigation).getByRole("link", { name: "Content" }),
    ).toBeInTheDocument();
    expect(
      within(navigation).getByRole("link", { name: "Catalog status" }),
    ).toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: "Learning paths" }),
    ).not.toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByTitle("Rigor API: Connected")).toBeInTheDocument(),
    );
  });
});
