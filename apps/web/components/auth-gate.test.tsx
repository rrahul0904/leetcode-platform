import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";

import { AuthGate } from "./auth-gate";
import { QueryProvider } from "./query-provider";

const router = { replace: vi.fn() };
const { getProfileMock } = vi.hoisted(() => ({ getProfileMock: vi.fn() }));

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
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getProfile: getProfileMock };
});

let pathname = "/";

function renderGate(label: string) {
  return render(
    <QueryProvider>
      <AuthGate>
        <div>{label}</div>
      </AuthGate>
    </QueryProvider>,
  );
}

beforeEach(() => {
  getProfileMock.mockResolvedValue({
    target_roles: ["Data engineer"],
    target_companies: [],
    experience_level: "senior",
    preferred_programming_language: "python",
    weekly_study_hours: 6,
    interview_date: null,
    strong_areas: [],
    weak_areas: [],
    preparation_intensity: "focused",
  });
});

afterEach(() => {
  cleanup();
  router.replace.mockClear();
  getProfileMock.mockReset();
});

describe("AuthGate", () => {
  it("returns a candidate with a stale admin destination to candidate home", async () => {
    pathname = "/admin/questions";
    renderGate("Admin content");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("forces a new candidate through onboarding", async () => {
    pathname = "/";
    getProfileMock.mockRejectedValueOnce(
      new ApiError(404, "Candidate profile not found"),
    );
    renderGate("Candidate home");
    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith("/onboarding"),
    );
    expect(screen.queryByText("Candidate home")).not.toBeInTheDocument();
  });

  it("allows onboarding when the candidate profile is missing", async () => {
    pathname = "/onboarding";
    getProfileMock.mockRejectedValueOnce(
      new ApiError(404, "Candidate profile not found"),
    );
    renderGate("Candidate onboarding");
    expect(await screen.findByText("Candidate onboarding")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalledWith("/onboarding");
  });

  it("opens the app for a candidate with a persisted profile", async () => {
    pathname = "/";
    renderGate("Candidate home");
    expect(await screen.findByText("Candidate home")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalledWith("/onboarding");
  });

  it("keeps a candidate inside the hosted practice workspace", async () => {
    pathname = "/practice/py-0001-bounded-cache";
    renderGate("Practice workspace");
    expect(await screen.findByText("Practice workspace")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalledWith("/");
  });
});
