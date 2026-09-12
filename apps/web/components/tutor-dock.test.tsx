import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TutorDock } from "./tutor-dock";

const createTutorSession = vi.fn();
const endTutorSession = vi.fn();
const listTutorEvents = vi.fn();
const listTutorSessions = vi.fn();
const sendTutorMessage = vi.fn();

vi.mock("@/lib/tutor-api", () => ({
  createTutorSession: (...args: unknown[]) => createTutorSession(...args),
  endTutorSession: (...args: unknown[]) => endTutorSession(...args),
  listTutorEvents: (...args: unknown[]) => listTutorEvents(...args),
  listTutorSessions: (...args: unknown[]) => listTutorSessions(...args),
  sendTutorMessage: (...args: unknown[]) => sendTutorMessage(...args),
}));

const session = {
  id: "00000000-0000-0000-0000-000000000101",
  mode: "practice",
  surface: "code",
  candidate_level: "senior",
  status: "active",
  question_slug: "reliable-event-aggregation",
  title: "Coding coach",
  provider: null,
  model: null,
  summary: null,
  started_at: "2026-09-12T00:00:00Z",
  updated_at: "2026-09-12T00:00:00Z",
  ended_at: null,
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("TutorDock", () => {
  it("restores a candidate-owned session and sends a coaching message", async () => {
    listTutorSessions.mockResolvedValue([session]);
    listTutorEvents.mockResolvedValue([
      {
        id: "event-user",
        session_id: session.id,
        event_type: "message.user",
        idempotency_key: "prior:user",
        payload: { message: "Can you review my approach?" },
        created_at: "2026-09-12T00:01:00Z",
      },
      {
        id: "event-assistant",
        session_id: session.id,
        event_type: "message.assistant",
        idempotency_key: "prior:assistant",
        payload: {
          message: "Start by naming the invariant your aggregation must preserve.",
          provider: "deterministic",
          model: "skillforge-socratic-v1",
        },
        created_at: "2026-09-12T00:01:01Z",
      },
    ]);
    sendTutorMessage.mockResolvedValue({
      session_id: session.id,
      reply: "What input would make your current assumption fail?",
      provider: "deterministic",
      model: "skillforge-socratic-v1",
      intervention: {
        kind: "hint",
        reason: "Candidate explicitly requested help.",
        may_reveal_solution: false,
        should_speak: true,
      },
    });

    render(<TutorDock slug="reliable-event-aggregation" />);

    fireEvent.click(screen.getByRole("button", { name: "Open AI tutor" }));

    expect(
      await screen.findByText("Start by naming the invariant your aggregation must preserve."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Senior · code-aware/)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Message AI tutor" }), {
      target: { value: "What edge case am I missing?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(sendTutorMessage).toHaveBeenCalledWith(
        session.id,
        "What edge case am I missing?",
        expect.stringMatching(/^web-/),
      ),
    );
    expect(
      await screen.findByText("What input would make your current assumption fail?"),
    ).toBeInTheDocument();
    expect(createTutorSession).not.toHaveBeenCalled();
  });

  it("creates a new code-aware practice session before the first message", async () => {
    listTutorSessions.mockResolvedValue([]);
    createTutorSession.mockResolvedValue({
      ...session,
      candidate_level: "mid",
    });
    sendTutorMessage.mockResolvedValue({
      session_id: session.id,
      reply: "Walk me through the state you need to carry between events.",
      provider: "deterministic",
      model: "skillforge-socratic-v1",
      intervention: {
        kind: "hint",
        reason: "Candidate explicitly requested help.",
        may_reveal_solution: false,
        should_speak: true,
      },
    });

    render(<TutorDock slug="reliable-event-aggregation" />);
    fireEvent.click(screen.getByRole("button", { name: "Open AI tutor" }));
    fireEvent.click(await screen.findByRole("button", { name: "Give me a hint" }));

    await waitFor(() =>
      expect(createTutorSession).toHaveBeenCalledWith({
        questionSlug: "reliable-event-aggregation",
        candidateLevel: "mid",
      }),
    );
    expect(
      await screen.findByText("Walk me through the state you need to carry between events."),
    ).toBeInTheDocument();
  });
});
