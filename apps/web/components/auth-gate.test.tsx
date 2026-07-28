import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthGate } from "./auth-gate";

const router = { replace: vi.fn() };

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => router,
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    status: "authenticated",
    principal: {
      authentication_provider: "local-oidc",
      display_name: "Casey Candidate",
      email: "candidate@rigor.test",
      roles: ["candidate"],
    },
    signOut: vi.fn(),
  }),
}));

let pathname = "/";

describe("AuthGate", () => {
  it("returns a candidate with a stale admin destination to candidate home", () => {
    pathname = "/admin/questions";
    render(
      <AuthGate>
        <div>Admin content</div>
      </AuthGate>,
    );
    expect(router.replace).toHaveBeenCalledWith("/");
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("opens the app for a new candidate without forcing onboarding", () => {
    pathname = "/";
    router.replace.mockClear();
    render(
      <AuthGate>
        <div>Candidate home</div>
      </AuthGate>,
    );
    expect(screen.getByText("Candidate home")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalledWith("/onboarding");
  });

  it("keeps a candidate inside the hosted practice workspace", () => {
    pathname = "/practice/py-0001-bounded-cache";
    router.replace.mockClear();
    render(
      <AuthGate>
        <div>Practice workspace</div>
      </AuthGate>,
    );
    expect(screen.getByText("Practice workspace")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalledWith("/");
  });
});
