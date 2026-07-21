import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthCallback } from "./auth-callback";

const mocks = vi.hoisted(() => ({
  completeSignIn: vi.fn(() => new Promise<void>(() => undefined)),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () =>
    new URLSearchParams("code=one-time-code&state=expected-state"),
}));

vi.mock("@/lib/auth", () => ({
  authReturnPath: () => "/",
  useAuth: () => ({ completeSignIn: mocks.completeSignIn }),
}));

describe("AuthCallback", () => {
  it("exchanges a one-time authorization code only once across rerenders", async () => {
    const view = render(<AuthCallback />);
    view.rerender(<AuthCallback />);
    await waitFor(() => expect(mocks.completeSignIn).toHaveBeenCalledTimes(1));
  });
});
