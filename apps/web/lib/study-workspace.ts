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

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
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
        compareText(left.task.dueOn ?? "9999-12-31", right.task.dueOn ?? "9999-12-31") ||
        left.task.estimatedMinutes - right.task.estimatedMinutes ||
        compareText(left.task.title, right.task.title) ||
        compareText(left.project.id, right.project.id) ||
        compareText(left.task.id, right.task.id),
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
    Math.min(4, card.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))),
  );

  let intervalDays = 1;
  if (!miss) {
    if (repetitions === 1) intervalDays = 1;
    else if (repetitions === 2) intervalDays = 6;
    else intervalDays = Math.min(36_500, Math.max(1, Math.round(card.intervalDays * ease)));
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

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function boundedText(value: unknown, maxLength: number): string | null {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maxLength
    ? value
    : null;
}

function validDateOnly(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year!, month! - 1, day!));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month! - 1 && parsed.getUTCDate() === day;
}

function validIsoDateTime(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString() === value;
}

function uniqueRows<T extends { id: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  return rows.filter(({ id }) => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

/** Validate untrusted browser storage before components or the planner use it. */
export function parseStudyWorkspace(value: unknown): StudyWorkspaceState | null {
  const source = record(value);
  if (source?.version !== 1 || !Array.isArray(source.projects) || !Array.isArray(source.flashcards)) {
    return null;
  }

  const projects = uniqueRows(source.projects.flatMap((item): StudyProject[] => {
    const row = record(item);
    const id = boundedText(row?.id, 100);
    const title = boundedText(row?.title, 160);
    const goal = row?.goal === "" || typeof row?.goal === "string" && row.goal.length <= 2000 ? row.goal : null;
    const targetDate = row?.targetDate === null || validDateOnly(row?.targetDate) ? row.targetDate : undefined;
    if (!row || !id || !title || goal === null || targetDate === undefined ||
        !Number.isSafeInteger(row.focusedMinutes) || Number(row.focusedMinutes) < 0 ||
        !Array.isArray(row.tasks) || row.tasks.length > 500 ||
        !Array.isArray(row.notes) || row.notes.length > 1000) return [];

    const tasks = uniqueRows(row.tasks.flatMap((taskValue): StudyTask[] => {
      const task = record(taskValue);
      const taskId = boundedText(task?.id, 100);
      const taskTitle = boundedText(task?.title, 300);
      const dueOn = task?.dueOn === null || validDateOnly(task?.dueOn) ? task.dueOn : undefined;
      if (!task || !taskId || !taskTitle || dueOn === undefined ||
          !Number.isSafeInteger(task.estimatedMinutes) || Number(task.estimatedMinutes) < 1 ||
          Number(task.estimatedMinutes) > 1440 || typeof task.completed !== "boolean") return [];
      return [{ id: taskId, title: taskTitle, dueOn, estimatedMinutes: Number(task.estimatedMinutes), completed: task.completed }];
    }));

    const notes = uniqueRows(row.notes.flatMap((noteValue): StudyNote[] => {
      const note = record(noteValue);
      const noteId = boundedText(note?.id, 100);
      if (!note || !noteId || !boundedText(note.body, 10_000) || !validIsoDateTime(note.createdAt)) return [];
      return [{ id: noteId, body: note.body as string, createdAt: note.createdAt }];
    }));

    return [{ id, title, goal, targetDate, focusedMinutes: Number(row.focusedMinutes), tasks, notes }];
  }));

  const projectIds = new Set(projects.map(({ id }) => id));
  const flashcards = uniqueRows(source.flashcards.flatMap((item): Flashcard[] => {
    const card = record(item);
    const id = boundedText(card?.id, 100);
    const projectId = boundedText(card?.projectId, 100);
    const front = boundedText(card?.front, 1000);
    const back = boundedText(card?.back, 5000);
    if (!card || !id || !projectId || !projectIds.has(projectId) || !front || !back ||
        typeof card.ease !== "number" || !Number.isFinite(card.ease) || card.ease < 1.3 || card.ease > 4 ||
        !Number.isSafeInteger(card.intervalDays) || Number(card.intervalDays) < 0 || Number(card.intervalDays) > 36_500 ||
        !Number.isSafeInteger(card.repetitions) || Number(card.repetitions) < 0 ||
        !validIsoDateTime(card.nextReviewAt) ||
        !(card.lastReviewedAt === null || validIsoDateTime(card.lastReviewedAt))) return [];
    return [{ id, projectId, front, back, ease: card.ease, intervalDays: Number(card.intervalDays), repetitions: Number(card.repetitions), nextReviewAt: card.nextReviewAt, lastReviewedAt: card.lastReviewedAt }];
  }));

  const activeProjectId = typeof source.activeProjectId === "string" && projectIds.has(source.activeProjectId)
    ? source.activeProjectId
    : projects[0]?.id ?? null;
  return { version: 1, activeProjectId, projects, flashcards };
}
