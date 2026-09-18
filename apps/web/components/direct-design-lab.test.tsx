import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DirectDesignLab } from "./direct-design-lab";

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
  id: "00000000-0000-0000-0000-000000000401",
  mode: "practice",
  surface: "whiteboard",
  candidate_level: "staff",
  status: "active",
  question_slug: null,
  title: "System design lab",
  provider: null,
  model: null,
  summary: null,
  started_at: "2026-09-14T15:00:00Z",
  updated_at: "2026-09-14T15:00:00Z",
  ended_at: null,
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("DirectDesignLab", () => {
  it("restores and persists a dragged node position", async () => {
    listTutorSessions.mockResolvedValue([session]);
    appendTutorEvent.mockResolvedValue({
      id: "event-autosave",
      session_id: session.id,
      event_type: "whiteboard.snapshot",
      idempotency_key: "autosave",
      payload: {},
      created_at: "2026-09-14T15:01:30Z",
    });
    listTutorEvents.mockResolvedValue([
      {
        id: "event-whiteboard",
        session_id: session.id,
        event_type: "whiteboard.snapshot",
        idempotency_key: "snapshot-1",
        payload: {
          nodes: [
            { id: "client", label: "Mobile client", kind: "client", x: 80, y: 90 },
            { id: "api", label: "API Gateway", kind: "gateway", x: 360, y: 90 },
          ],
          edges: [{ source: "client", target: "api", label: "HTTPS" }],
          requirements: ["99.99% availability"],
          notes: ["Stateless edge routing"],
        },
        created_at: "2026-09-14T15:01:00Z",
      },
    ]);

    render(<DirectDesignLab />);

    const handle = await screen.findByRole("button", { name: "Move Mobile client" });
    const stage = screen.getByRole("region", { name: "Architecture canvas" });

    fireEvent.pointerDown(handle, { clientX: 100, clientY: 110, pointerId: 1 });
    fireEvent.pointerMove(stage, { clientX: 470, clientY: 300, pointerId: 1 });
    fireEvent.pointerUp(stage, { clientX: 470, clientY: 300, pointerId: 1 });

    await waitFor(() => {
      const stored = window.localStorage.getItem("rigor-design-lab-draft-v3");
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored ?? "{}") as {
        nodes?: Array<{ id: string; x: number; y: number }>;
      };
      const client = parsed.nodes?.find((node) => node.id === "client");
      expect(client?.x).toBeGreaterThan(80);
      expect(client?.y).toBeGreaterThan(90);
    });
  });

  it("persists the board before a one-click interview probe", async () => {
    listTutorSessions.mockResolvedValue([]);
    listTutorEvents.mockResolvedValue([]);
    createWhiteboardTutorSession.mockResolvedValue(session);
    appendTutorEvent.mockResolvedValue({
      id: "event-new",
      session_id: session.id,
      event_type: "whiteboard.snapshot",
      idempotency_key: "snapshot-new",
      payload: {},
      created_at: "2026-09-14T15:02:00Z",
    });
    sendTutorMessage.mockResolvedValue({
      session_id: session.id,
      reply: "Which component saturates first, and what metric would prove it?",
      provider: "skillforge",
      model: "socratic-v1",
      intervention: {
        kind: "tradeoff_challenge",
        reason: "structured design is ready for a trade-off probe",
        may_reveal_solution: false,
        should_speak: true,
      },
    });

    render(<DirectDesignLab />);

    fireEvent.click(await screen.findByRole("button", { name: "Find bottleneck" }));

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
      "Find the bottleneck in this design. Ask me to quantify why it is the bottleneck.",
      expect.stringMatching(/^design-tutor-/),
    );
    expect(
      await screen.findByText("Which component saturates first, and what metric would prove it?"),
    ).toBeInTheDocument();
  });
});
