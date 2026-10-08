import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThinkAloudWorkspace } from "./think-aloud-workspace";

const apiMocks = vi.hoisted(() => ({
  commitThinkAloudTurn: vi.fn(),
  createThinkAloudSession: vi.fn(),
  getThinkAloudSession: vi.fn(),
  mutateThinkAloudCanvas: vi.fn(),
  recordThinkAloudEvent: vi.fn(),
  resumeThinkAloudCoaching: vi.fn(),
  startThinkAloudCoaching: vi.fn(),
}));

vi.mock("@/lib/think-aloud-api", () => apiMocks);

const baseSession = {
  session: {
    id: "00000000-0000-0000-0000-000000000701",
    interview_type: "TECHNICAL_MOCK",
    target_role: "Staff Software Engineer",
    focus: "system-design",
    focus_label: "System design",
    status: "IN_PROGRESS" as const,
    current_phase: "requirements",
    started_at: "2026-10-08T03:00:00Z",
    completed_at: null,
    created_at: "2026-10-08T03:00:00Z",
    updated_at: "2026-10-08T03:00:00Z",
    messages: [
      {
        id: "00000000-0000-0000-0000-000000000702",
        session_id: "00000000-0000-0000-0000-000000000701",
        sequence_number: 0,
        role: "interviewer",
        phase: "requirements",
        content: "Design a globally available notification service.",
        evidence: {},
        created_at: "2026-10-08T03:00:00Z",
      },
    ],
    report: null,
  },
  control: {
    session_id: "00000000-0000-0000-0000-000000000701",
    mode: "practice" as const,
    floor_owner: "candidate" as const,
    coaching_active: false,
    provider_connected: true,
    events: [],
    canvas: [],
  },
};

const withCanvas = {
  ...baseSession,
  control: {
    ...baseSession.control,
    canvas: [
      {
        sequence_number: 2,
        role: "canvas",
        phase: "requirements",
        event_type: "canvas_mutation",
        content: "Notification API",
        payload: { kind: "add_component", component_type: "service" },
        created_at: "2026-10-08T03:01:00Z",
      },
    ],
  },
};

const coachingSession = {
  ...withCanvas,
  session: {
    ...withCanvas.session,
    status: "PAUSED" as const,
    messages: [
      ...withCanvas.session.messages,
      {
        id: "00000000-0000-0000-0000-000000000703",
        session_id: withCanvas.session.id,
        sequence_number: 3,
        role: "coach",
        phase: "requirements",
        content: "State assumptions first, then make one concrete design decision.",
        evidence: {},
        created_at: "2026-10-08T03:02:00Z",
      },
    ],
  },
  control: {
    ...withCanvas.control,
    floor_owner: "coach" as const,
    coaching_active: true,
  },
};

const assessmentSession = {
  ...baseSession,
  control: {
    ...baseSession.control,
    mode: "assessment" as const,
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  apiMocks.createThinkAloudSession.mockResolvedValue(baseSession);
  apiMocks.getThinkAloudSession.mockResolvedValue(baseSession);
  apiMocks.recordThinkAloudEvent.mockResolvedValue(baseSession);
  apiMocks.mutateThinkAloudCanvas.mockResolvedValue(withCanvas);
  apiMocks.startThinkAloudCoaching.mockResolvedValue(coachingSession);
  apiMocks.resumeThinkAloudCoaching.mockResolvedValue(withCanvas);
  apiMocks.commitThinkAloudTurn.mockResolvedValue(baseSession);
});

describe("ThinkAloudWorkspace", () => {
  it("keeps thinking separate from turn commit and persists canvas and coaching", async () => {
    render(<ThinkAloudWorkspace />);

    expect(
      screen.getByRole("heading", { name: /practice system design like a real conversation/i }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /start think aloud interview/i }));

    expect(
      await screen.findByText("Design a globally available notification service."),
    ).toBeInTheDocument();
    expect(apiMocks.createThinkAloudSession).toHaveBeenCalledWith(
      "system-design",
      "Staff Software Engineer",
      "practice",
      expect.any(String),
    );

    fireEvent.click(screen.getByRole("button", { name: /i’m thinking/i }));
    await waitFor(() => {
      expect(apiMocks.recordThinkAloudEvent).toHaveBeenCalledWith(
        baseSession.session.id,
        "candidate_silence",
        { source: "candidate_thinking_control" },
        expect.any(String),
      );
    });
    expect(await screen.findByText(/you still own the floor/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Canvas component label"), {
      target: { value: "Notification API" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add to canvas/i }));
    expect(await screen.findByText("Notification API")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /pause for coaching/i }));
    expect(
      await screen.findByText(/state assumptions first, then make one concrete design decision/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /resume interview/i })).toBeInTheDocument();
  });

  it("advances only through the explicit done-speaking action", async () => {
    render(<ThinkAloudWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: /start think aloud interview/i }));
    await screen.findByText("Design a globally available notification service.");

    fireEvent.change(screen.getByLabelText("Candidate response"), {
      target: {
        value: "I would clarify latency, availability, scale, and the product scope first.",
      },
    });
    expect(apiMocks.commitThinkAloudTurn).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /done speaking/i }));
    await waitFor(() => {
      expect(apiMocks.commitThinkAloudTurn).toHaveBeenCalledWith(
        baseSession.session.id,
        "I would clarify latency, availability, scale, and the product scope first.",
        expect.any(String),
      );
    });
  });

  it("locks coaching in assessment mode", async () => {
    apiMocks.createThinkAloudSession.mockResolvedValue(assessmentSession);
    render(<ThinkAloudWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /assessment/i }));
    fireEvent.click(screen.getByRole("button", { name: /start think aloud interview/i }));

    expect(await screen.findByText("Assessment isolation")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pause for coaching/i })).not.toBeInTheDocument();
    expect(apiMocks.createThinkAloudSession).toHaveBeenCalledWith(
      "system-design",
      "Staff Software Engineer",
      "assessment",
      expect.any(String),
    );
  });
});
