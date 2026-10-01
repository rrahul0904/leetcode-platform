"use client";

import {
  BookOpen,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Layers3,
  Plus,
  RotateCcw,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  buildDailyPlan,
  EMPTY_STUDY_WORKSPACE,
  isCardDue,
  reviewFlashcard,
  type ReviewRating,
  type StudyWorkspaceState,
} from "@/lib/study-workspace";

import styles from "./study-workspace.module.css";

const STORAGE_KEY = "skillforge.study-workspace.v1";
const REVIEW_LABELS: Array<{ rating: ReviewRating; label: string }> = [
  { rating: 1, label: "Again" },
  { rating: 2, label: "Hard" },
  { rating: 3, label: "Good" },
  { rating: 4, label: "Easy" },
  { rating: 5, label: "Perfect" },
];

function id(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatDueDate(value: string | null) {
  if (!value) return "No due date";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

export function StudyWorkspace() {
  const [workspace, setWorkspace] = useState<StudyWorkspaceState>(EMPTY_STUDY_WORKSPACE);
  const [hydrated, setHydrated] = useState(false);
  const [projectTitle, setProjectTitle] = useState("");
  const [projectGoal, setProjectGoal] = useState("");
  const [projectDate, setProjectDate] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDate, setTaskDate] = useState("");
  const [taskMinutes, setTaskMinutes] = useState("30");
  const [noteBody, setNoteBody] = useState("");
  const [cardFront, setCardFront] = useState("");
  const [cardBack, setCardBack] = useState("");
  const [revealedCardId, setRevealedCardId] = useState<string | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as StudyWorkspaceState;
        if (parsed.version === 1 && Array.isArray(parsed.projects) && Array.isArray(parsed.flashcards)) {
          setWorkspace(parsed);
        }
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace));
  }, [hydrated, workspace]);

  const activeProject =
    workspace.projects.find((project) => project.id === workspace.activeProjectId) ??
    workspace.projects[0] ??
    null;

  const dailyPlan = useMemo(
    () => buildDailyPlan(workspace.projects, 90),
    [workspace.projects],
  );

  const dueCards = useMemo(() => {
    const now = new Date();
    return workspace.flashcards.filter((card) => isCardDue(card, now));
  }, [workspace.flashcards]);

  const nextCard = dueCards[0] ?? null;

  function addProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = projectTitle.trim();
    if (!title) return;
    const projectId = id("project");
    setWorkspace((current) => ({
      ...current,
      activeProjectId: projectId,
      projects: [
        ...current.projects,
        {
          id: projectId,
          title,
          goal: projectGoal.trim(),
          targetDate: projectDate || null,
          focusedMinutes: 0,
          tasks: [],
          notes: [],
        },
      ],
    }));
    setProjectTitle("");
    setProjectGoal("");
    setProjectDate("");
  }

  function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProject) return;
    const title = taskTitle.trim();
    const estimatedMinutes = Math.max(5, Number.parseInt(taskMinutes, 10) || 30);
    if (!title) return;
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === activeProject.id
          ? {
              ...project,
              tasks: [
                ...project.tasks,
                {
                  id: id("task"),
                  title,
                  dueOn: taskDate || null,
                  estimatedMinutes,
                  completed: false,
                },
              ],
            }
          : project,
      ),
    }));
    setTaskTitle("");
    setTaskDate("");
    setTaskMinutes("30");
  }

  function toggleTask(taskId: string) {
    if (!activeProject) return;
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === activeProject.id
          ? {
              ...project,
              tasks: project.tasks.map((task) =>
                task.id === taskId ? { ...task, completed: !task.completed } : task,
              ),
            }
          : project,
      ),
    }));
  }

  function completeFocusBlock() {
    if (!activeProject) return;
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === activeProject.id
          ? { ...project, focusedMinutes: project.focusedMinutes + 25 }
          : project,
      ),
    }));
  }

  function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProject || !noteBody.trim()) return;
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) =>
        project.id === activeProject.id
          ? {
              ...project,
              notes: [
                {
                  id: id("note"),
                  body: noteBody.trim(),
                  createdAt: new Date().toISOString(),
                },
                ...project.notes,
              ],
            }
          : project,
      ),
    }));
    setNoteBody("");
  }

  function addFlashcard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProject || !cardFront.trim() || !cardBack.trim()) return;
    setWorkspace((current) => ({
      ...current,
      flashcards: [
        ...current.flashcards,
        {
          id: id("card"),
          projectId: activeProject.id,
          front: cardFront.trim(),
          back: cardBack.trim(),
          ease: 2.5,
          intervalDays: 0,
          repetitions: 0,
          nextReviewAt: new Date().toISOString(),
          lastReviewedAt: null,
        },
      ],
    }));
    setCardFront("");
    setCardBack("");
  }

  function rateCard(rating: ReviewRating) {
    if (!nextCard) return;
    setWorkspace((current) => ({
      ...current,
      flashcards: current.flashcards.map((card) =>
        card.id === nextCard.id ? reviewFlashcard(card, rating, new Date()) : card,
      ),
    }));
    setRevealedCardId(null);
  }

  if (!hydrated) {
    return <main className={styles.shell}>Restoring your study workspace…</main>;
  }

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <Layers3 size={15} /> STUDY WORKSPACE
          </span>
          <h1>Plan the work, practice the skill, keep the evidence.</h1>
          <p>
            A clean-room learning workspace for projects, daily study blocks, notes,
            focus time, and spaced review. AI coaching stays in the existing SkillForge
            tutor so this does not create a second learning system.
          </p>
        </div>
        <div className={styles.heroActions}>
          <Link href="/learning-paths">
            <Target size={16} /> Learning paths
          </Link>
          <Link href="/question-bank">
            <BrainCircuit size={16} /> Practice with tutor
          </Link>
        </div>
      </header>

      <section className={styles.summaryGrid}>
        <article>
          <CalendarDays size={20} />
          <span>Today&apos;s plan</span>
          <strong>{dailyPlan.reduce((sum, block) => sum + block.minutes, 0)} min</strong>
          <small>{dailyPlan.length} focused block{dailyPlan.length === 1 ? "" : "s"}</small>
        </article>
        <article>
          <RotateCcw size={20} />
          <span>Review queue</span>
          <strong>{dueCards.length}</strong>
          <small>{workspace.flashcards.length} cards total</small>
        </article>
        <article>
          <Clock3 size={20} />
          <span>Focus bank</span>
          <strong>{workspace.projects.reduce((sum, project) => sum + project.focusedMinutes, 0)} min</strong>
          <small>Evidence recorded locally</small>
        </article>
      </section>

      <section className={styles.twoColumn}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.kicker}>PROJECTS</span>
              <h2>Study outcomes</h2>
            </div>
            {workspace.projects.length > 0 && (
              <select
                aria-label="Active study project"
                onChange={(event) =>
                  setWorkspace((current) => ({
                    ...current,
                    activeProjectId: event.target.value,
                  }))
                }
                value={activeProject?.id ?? ""}
              >
                {workspace.projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.title}
                  </option>
                ))}
              </select>
            )}
          </div>

          <form className={styles.compactForm} onSubmit={addProject}>
            <input
              aria-label="Project title"
              onChange={(event) => setProjectTitle(event.target.value)}
              placeholder="Course, certification, interview…"
              value={projectTitle}
            />
            <input
              aria-label="Project goal"
              onChange={(event) => setProjectGoal(event.target.value)}
              placeholder="Outcome you want to reach"
              value={projectGoal}
            />
            <input
              aria-label="Project target date"
              onChange={(event) => setProjectDate(event.target.value)}
              type="date"
              value={projectDate}
            />
            <button type="submit">
              <Plus size={15} /> Add project
            </button>
          </form>

          {!activeProject ? (
            <div className={styles.empty}>
              Add your first study project. The workspace will turn its tasks into a
              lightweight daily plan.
            </div>
          ) : (
            <>
              <div className={styles.projectMeta}>
                <div>
                  <strong>{activeProject.title}</strong>
                  <span>{activeProject.goal || "No outcome written yet."}</span>
                </div>
                <small>{activeProject.targetDate ? `Target ${formatDueDate(activeProject.targetDate)}` : "Open-ended"}</small>
              </div>

              <form className={styles.taskForm} onSubmit={addTask}>
                <input
                  aria-label="Task title"
                  onChange={(event) => setTaskTitle(event.target.value)}
                  placeholder="Next concrete study task"
                  value={taskTitle}
                />
                <input
                  aria-label="Task due date"
                  onChange={(event) => setTaskDate(event.target.value)}
                  type="date"
                  value={taskDate}
                />
                <input
                  aria-label="Task minutes"
                  min="5"
                  onChange={(event) => setTaskMinutes(event.target.value)}
                  step="5"
                  type="number"
                  value={taskMinutes}
                />
                <button type="submit">Add task</button>
              </form>

              <div className={styles.taskList}>
                {activeProject.tasks.map((task) => (
                  <button
                    className={task.completed ? styles.taskDone : styles.task}
                    key={task.id}
                    onClick={() => toggleTask(task.id)}
                    type="button"
                  >
                    <CheckCircle2 size={16} />
                    <span>
                      <strong>{task.title}</strong>
                      <small>{formatDueDate(task.dueOn)} · {task.estimatedMinutes} min</small>
                    </span>
                  </button>
                ))}
                {activeProject.tasks.length === 0 && (
                  <div className={styles.empty}>No tasks yet. Add a concrete next action.</div>
                )}
              </div>
            </>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.kicker}>TODAY</span>
              <h2>Adaptive study plan</h2>
            </div>
            <span className={styles.badge}>90 min budget</span>
          </div>

          <div className={styles.planList}>
            {dailyPlan.map((block, index) => (
              <article key={block.taskId}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{block.taskTitle}</strong>
                  <small>{block.projectTitle} · {formatDueDate(block.dueOn)}</small>
                </div>
                <b>{block.minutes}m</b>
              </article>
            ))}
            {dailyPlan.length === 0 && (
              <div className={styles.empty}>Add incomplete tasks to generate today&apos;s plan.</div>
            )}
          </div>

          <button
            className={styles.focusButton}
            disabled={!activeProject}
            onClick={completeFocusBlock}
            type="button"
          >
            <Clock3 size={17} /> Record 25-minute focus block
          </button>
        </div>
      </section>

      <section className={styles.twoColumn}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.kicker}>ACTIVE RECALL</span>
              <h2>Spaced review</h2>
            </div>
            <span className={styles.badge}>{dueCards.length} due</span>
          </div>

          {nextCard ? (
            <div className={styles.reviewCard}>
              <span>QUESTION</span>
              <h3>{nextCard.front}</h3>
              {revealedCardId === nextCard.id ? (
                <>
                  <p>{nextCard.back}</p>
                  <div className={styles.ratingRow}>
                    {REVIEW_LABELS.map(({ rating, label }) => (
                      <button key={rating} onClick={() => rateCard(rating)} type="button">
                        <b>{rating}</b>
                        <span>{label}</span>
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <button onClick={() => setRevealedCardId(nextCard.id)} type="button">
                  Reveal answer
                </button>
              )}
            </div>
          ) : (
            <div className={styles.empty}>No cards are due right now.</div>
          )}

          <form className={styles.cardForm} onSubmit={addFlashcard}>
            <input
              aria-label="Flashcard question"
              disabled={!activeProject}
              onChange={(event) => setCardFront(event.target.value)}
              placeholder="Question / prompt"
              value={cardFront}
            />
            <textarea
              aria-label="Flashcard answer"
              disabled={!activeProject}
              onChange={(event) => setCardBack(event.target.value)}
              placeholder="Answer"
              rows={3}
              value={cardBack}
            />
            <button disabled={!activeProject} type="submit">
              <Plus size={15} /> Add review card
            </button>
          </form>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.kicker}>NOTES</span>
              <h2>Learning log</h2>
            </div>
            <BookOpen size={20} />
          </div>

          <form className={styles.noteForm} onSubmit={addNote}>
            <textarea
              aria-label="Study note"
              disabled={!activeProject}
              onChange={(event) => setNoteBody(event.target.value)}
              placeholder="Capture a concept, mistake, question, or reflection…"
              rows={5}
              value={noteBody}
            />
            <button disabled={!activeProject} type="submit">Save note</button>
          </form>

          <div className={styles.noteList}>
            {(activeProject?.notes ?? []).map((note) => (
              <article key={note.id}>
                <p>{note.body}</p>
                <small>{new Date(note.createdAt).toLocaleString()}</small>
              </article>
            ))}
            {(activeProject?.notes.length ?? 0) === 0 && (
              <div className={styles.empty}>Your project notes will stay on this device in this MVP slice.</div>
            )}
          </div>
        </div>
      </section>

      <section className={styles.boundary}>
        <Sparkles size={20} />
        <div>
          <strong>Clean-room capability donor</strong>
          <p>
            This slice reproduces public product behavior, not Mookti source code,
            proprietary content, visual assets, or branding. Server persistence,
            document ingestion, calendar sync, transcription, billing credits, and
            rich PDF/handwriting remain explicit follow-on work.
          </p>
        </div>
      </section>
    </main>
  );
}
