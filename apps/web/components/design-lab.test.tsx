import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DesignLab } from "./design-lab";

const appendTutorEvent = vi.fn();
const createWhiteboardTutorSession = vi.fn();
const listTutorEvents = vi.fn();
const listTutorSessions = vi.fn();
const sendTutorMessage = vi.fn();

vi.mock("@/lib/tutor-api", () => ({
  appendTutorEvent: (...args: unknown[]) => appendTutorEvent(...args),
  createWhiteboardTutorSession: (...args: unknown[]) => createWhiteboardTutorSession(...args),
  listTutorEvents: (...args: unknown[]) => listTutorEvents(...args),
  listTutorSessions: (...args: unknown[]) => listTutorSessions(...args),
  sendTutorMessage: (...args: unknown[]) => sendTutorMessage(...args),
}));

const session = {
  id: "00000000-0000-0000-0000-000000000301",
  mode: "practice",
  surface: "whiteboard",
  candidate_level: "staff",
  status: "active",
  question_slug: null,
  title: "System design lab",
  provider: null,
  model: null,
  summary: null,
  started_at: "2026-09-14T12:00:00Z",
  updated_at: "2026-09-14T12:00:00Z",
  ended_at: null,
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("DesignLab", () => {
  it("restores a candidate-owned whiteboard snapshot", async () => {
    listTutorSessions.mockResolvedValue([session]);
    listTutorEvents.mockResolvedValue([
      {
        id: "event-whiteboard",
        session_id: session.id,
        event_type: "whiteboard.snapshot",
        idempotency_key: "snapshot-1",
        payload: {
          nodes: [
            { id: "client", label: "Mobile client", kind: "client", x: 80, y: 90 },
            { id: "api", label: "API Gateway", kind: "gateway", x: 270, y: 90 },
          ],
          edges: [{ source: "client", target: "api", label: "HTTPS" }],
          requirements: ["99.99% availability"],
          notes: ["Prefer stateless edge routing"],
        },
        created_at: "2026-09-14T12:01:00Z",
      },
    ]);

    render(<DesignLab />);

    expect((await screen.findAllByText("Mobile client")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("API Gateway").length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue(/99.99% availability/)).toBeInTheDocument();
    expect(screen.getByText(/Account-backed design session restored/)).toBeInTheDocument();
  });

  it("persists the current board before asking the architecture tutor", async () => {
    listTutorSessions.mockResolvedValue([]);
    createWhiteboardTutorSession.mockResolvedValue(session);
    appendTutorEvent.mockResolvedValue({
      id: "event-new",
      session_id: session.id,
      event_type: "whiteboard.snapshot",
      idempotency_key: "snapshot-new",
      payload: {},
      created_at: "2026-09-14T12:02:00Z",
    });
    sendTutorMessage.mockResolvedValue({
      session_id: session.id,
      reply: "Which component owns durability, and what fails if it becomes unavailable?",
      provider: "skillforge",
      model: "socratic-v1",
      intervention: {
        kind: "hint",
        reason: "candidate explicitly requested help",
        may_reveal_solution: false,
        should_speak: true,
      },
    });

    render(<DesignLab />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Ask architecture tutor" }), {
      target: { value: "Challenge my failure modes" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask tutor" }));

    await waitFor(() =>
      expect(createWhiteboardTutorSession).toHaveBeenCalledWith({
        candidateLevel: "senior",
        title: expect.stringMatching(/^Untitled /),
      }),
    );
    await waitFor(() =>
      expect(appendTutorEvent).toHaveBeenCalledWith(
        session.id,
        expect.objectContaining({
          eventType: "whiteboard.snapshot",
          payload: expect.objectContaining({
            nodes: expect.any(Array),
            edges: expect.any(Array),
          }),
        }),
      ),
    );
    expect(sendTutorMessage).toHaveBeenCalledWith(
      session.id,
      "Challenge my failure modes",
      expect.stringMatching(/^design-tutor-/),
    );
    expect(
      await screen.findByText(
        "Which component owns durability, and what fails if it becomes unavailable?",
      ),
    ).toBeInTheDocument();
  });
});
