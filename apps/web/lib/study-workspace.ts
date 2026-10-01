export type ReviewRating = 1 | 2 | 3 | 4 | 5;

export type StudyTask = {
  id: string;
  title: string;
  dueOn: string | null;
  estimatedMinutes: number;
  completed: boolean;
};

export type StudyNote = {
  id: string;
  body: string;
  createdAt: string;
};

export type StudyProject = {
  id: string;
  title: string;
  goal: string;
  targetDate: string | null;
  focusedMinutes: number;
  tasks: StudyTask[];
  notes: StudyNote[];
};

export type Flashcard = {
  id: string;
  projectId: string;
  front: string;
  back: string;
  ease: number;
  intervalDays: number;
  repetitions: number;
  nextReviewAt: string;
  lastReviewedAt: string | null;
};

export type StudyWorkspaceState = {
  version: 1;
  activeProjectId: string | null;
  projects: StudyProject[];
  flashcards: Flashcard[];
};

export type PlannedBlock = {
  projectId: string;
  projectTitle: string;
  taskId: string;
  taskTitle: string;
  minutes: number;
  dueOn: string | null;
};

export const EMPTY_STUDY_WORKSPACE: StudyWorkspaceState = {
  version: 1,
  activeProjectId: null,
  projects: [],
  flashcards: [],
};

function parseDueDate(value: string | null): number {
  if (!value) return Number.POSITIVE_INFINITY;
  const timestamp = Date.parse(`${value}T12:00:00`);
  return Number.isNaN(timestamp) ? Number.POSITIVE_INFINITY : timestamp;
}

export function buildDailyPlan(
  projects: StudyProject[],
  availableMinutes: number,
): PlannedBlock[] {
  if (availableMinutes <= 0) return [];

  const candidates = projects
    .flatMap((project) =>
      project.tasks
        .filter((task) => !task.completed)
        .map((task) => ({ project, task })),
    )
    .sort(
      (left, right) =>
        parseDueDate(left.task.dueOn) - parseDueDate(right.task.dueOn) ||
        left.task.estimatedMinutes - right.task.estimatedMinutes ||
        left.task.title.localeCompare(right.task.title),
    );

  let remaining = Math.floor(availableMinutes);
  const plan: PlannedBlock[] = [];

  for (const { project, task } of candidates) {
    if (remaining <= 0) break;
    const minutes = Math.min(Math.max(1, task.estimatedMinutes), remaining);
    plan.push({
      projectId: project.id,
      projectTitle: project.title,
      taskId: task.id,
      taskTitle: task.title,
      minutes,
      dueOn: task.dueOn,
    });
    remaining -= minutes;
  }

  return plan;
}

export function reviewFlashcard(
  card: Flashcard,
  rating: ReviewRating,
  reviewedAt: Date,
): Flashcard {
  const quality = rating;
  const miss = quality < 3;
  const repetitions = miss ? 0 : card.repetitions + 1;
  const ease = Math.max(
    1.3,
    card.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
  );

  let intervalDays = 1;
  if (!miss) {
    if (repetitions === 1) intervalDays = 1;
    else if (repetitions === 2) intervalDays = 6;
    else intervalDays = Math.max(1, Math.round(card.intervalDays * ease));
  }

  const nextReview = new Date(reviewedAt);
  nextReview.setUTCDate(nextReview.getUTCDate() + intervalDays);

  return {
    ...card,
    ease: Number(ease.toFixed(2)),
    intervalDays,
    repetitions,
    lastReviewedAt: reviewedAt.toISOString(),
    nextReviewAt: nextReview.toISOString(),
  };
}

export function isCardDue(card: Flashcard, now: Date): boolean {
  const timestamp = Date.parse(card.nextReviewAt);
  return Number.isNaN(timestamp) || timestamp <= now.getTime();
}
