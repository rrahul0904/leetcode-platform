import { describe, expect, it } from "vitest";

import {
  buildDailyPlan,
  reviewFlashcard,
  type Flashcard,
  type StudyProject,
} from "./study-workspace";

describe("study workspace domain", () => {
  it("prioritizes incomplete work by due date within the available time", () => {
    const projects: StudyProject[] = [
      {
        id: "project-1",
        title: "Distributed systems",
        goal: "Finish the reliability module",
        targetDate: "2026-10-01",
        focusedMinutes: 0,
        notes: [],
        tasks: [
          {
            id: "later",
            title: "Read consensus notes",
            dueOn: "2026-09-30",
            estimatedMinutes: 45,
            completed: false,
          },
          {
            id: "first",
            title: "Practice replication failures",
            dueOn: "2026-09-22",
            estimatedMinutes: 60,
            completed: false,
          },
          {
            id: "done",
            title: "Completed task",
            dueOn: "2026-09-21",
            estimatedMinutes: 20,
            completed: true,
          },
        ],
      },
    ];

    expect(buildDailyPlan(projects, 75)).toEqual([
      expect.objectContaining({ taskId: "first", minutes: 60 }),
      expect.objectContaining({ taskId: "later", minutes: 15 }),
    ]);
  });

  it("uses SM-2 style recovery after a failed recall", () => {
    const card: Flashcard = {
      id: "card-1",
      projectId: "project-1",
      front: "What is quorum intersection?",
      back: "Any two quorums share at least one member.",
      ease: 2.5,
      intervalDays: 10,
      repetitions: 4,
      nextReviewAt: "2026-09-21T12:00:00.000Z",
      lastReviewedAt: null,
    };

    const reviewed = reviewFlashcard(card, 1, new Date("2026-09-21T15:00:00.000Z"));

    expect(reviewed.repetitions).toBe(0);
    expect(reviewed.intervalDays).toBe(1);
    expect(reviewed.nextReviewAt).toBe("2026-09-22T15:00:00.000Z");
    expect(reviewed.ease).toBeGreaterThanOrEqual(1.3);
  });

  it("expands the interval after successful repeated recall", () => {
    const card: Flashcard = {
      id: "card-2",
      projectId: "project-1",
      front: "CAP theorem",
      back: "Consistency, availability, partition tolerance.",
      ease: 2.5,
      intervalDays: 6,
      repetitions: 2,
      nextReviewAt: "2026-09-21T12:00:00.000Z",
      lastReviewedAt: null,
    };

    const reviewed = reviewFlashcard(card, 5, new Date("2026-09-21T15:00:00.000Z"));

    expect(reviewed.repetitions).toBe(3);
    expect(reviewed.intervalDays).toBeGreaterThan(6);
  });
});
