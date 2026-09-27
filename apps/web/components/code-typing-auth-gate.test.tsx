import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthGate } from "./auth-gate";
import { QueryProvider } from "./query-provider";

const { replace, getProfile } = vi.hoisted(() => ({ replace: vi.fn(), getProfile: vi.fn() }));
let pathname = "/practice/code-typing";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ principal: null, status: "anonymous" }),
}));
vi.mock("@/lib/api", () => ({
  getProfile,
  ApiError: class ApiError extends Error {},
}));

afterEach(() => {
  cleanup();
  replace.mockClear();
  getProfile.mockClear();
});

describe("narrow guest practice access", () => {
  function visit(path: string) {
    pathname = path;
    return render(
      <QueryProvider>
        <AuthGate><span>Practice content</span></AuthGate>
      </QueryProvider>,
    );
  }
  it("allows anonymous access to code typing without profile API calls or redirects", () => {
    visit("/practice/code-typing");
    expect(screen.getByText("Practice content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(getProfile).not.toHaveBeenCalled();
  });
  it("does not make the other practice routes public", async () => {
    visit("/practice/py-0001-bounded-cache");
    expect(screen.queryByText("Practice content")).not.toBeInTheDocument();
    await waitFor(() => expect(replace).toHaveBeenCalledWith(
      "/sign-in?returnTo=%2Fpractice%2Fpy-0001-bounded-cache",
    ));
  });
});
