"use client";

import {
  BookOpen,
  Check,
  Code2,
  Compass,
  Eye,
  EyeOff,
  Lightbulb,
  MessageSquareText,
  Mountain,
} from "lucide-react";
import { useEffect, useState } from "react";

import styles from "./guided-practice-journey.module.css";

type LearningStage = "study" | "discover" | "practice" | "create" | "challenge";

type StoredJourney = {
  activeStage: LearningStage;
  completed: LearningStage[];
  reflection: string;
  focusMode: boolean;
};

type GuidedPracticeJourneyProps = {
  slug: string;
  learningObjectives: string[];
  constraints: string[];
  onFocusModeChange?: (enabled: boolean) => void;
};

const STAGES: Array<{
  id: LearningStage;
  label: string;
  caption: string;
  icon: typeof BookOpen;
}> = [
  { id: "study", label: "Study", caption: "Understand the goal", icon: BookOpen },
  { id: "discover", label: "Discover", caption: "Notice constraints", icon: Compass },
  { id: "practice", label: "Practice", caption: "Explain your approach", icon: MessageSquareText },
  { id: "create", label: "Create", caption: "Build and test it", icon: Code2 },
  { id: "challenge", label: "Challenge", caption: "Stretch the reasoning", icon: Mountain },
];

const STAGE_IDS = STAGES.map((stage) => stage.id);

const NUDGES: Record<LearningStage, string> = {
  study:
    "Before coding, say what the input represents, what the output must guarantee, and what would make an answer invalid.",
  discover:
    "Look for a boundary, an empty or minimal case, and one constraint that should influence your data structure or query shape.",
  practice:
    "Explain why your planned approach should work before describing syntax. Then state the expected time and space cost.",
  create:
    "Name the invariant your code should preserve after each meaningful step. If you get stuck, trace one tiny example by hand.",
  challenge:
    "Imagine the input is 10× larger or arrives continuously. Which assumption breaks first, and what trade-off would you revisit?",
};

const DEFAULT_JOURNEY: StoredJourney = {
  activeStage: "study",
  completed: [],
  reflection: "",
  focusMode: false,
};

function isLearningStage(value: unknown): value is LearningStage {
  return typeof value === "string" && STAGE_IDS.includes(value as LearningStage);
}

function normaliseStoredJourney(value: unknown): StoredJourney {
  if (!value || typeof value !== "object") return DEFAULT_JOURNEY;
  const candidate = value as Partial<StoredJourney>;
  const completed = Array.isArray(candidate.completed)
    ? candidate.completed.filter(isLearningStage)
    : [];
  return {
    activeStage: isLearningStage(candidate.activeStage) ? candidate.activeStage : "study",
    completed: Array.from(new Set(completed)),
    reflection: typeof candidate.reflection === "string" ? candidate.reflection : "",
    focusMode: candidate.focusMode === true,
  };
}

export function GuidedPracticeJourney({
  slug,
  learningObjectives,
  constraints,
  onFocusModeChange,
}: GuidedPracticeJourneyProps) {
  const [journey, setJourney] = useState<StoredJourney>(DEFAULT_JOURNEY);
  const [hydrated, setHydrated] = useState(false);
  const [showNudge, setShowNudge] = useState(false);
  const storageKey = `skillsforge.guided-practice:${slug}`;

  useEffect(() => {
    let restoredJourney: StoredJourney | undefined;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) restoredJourney = normaliseStoredJourney(JSON.parse(raw));
    } catch {
      // A corrupt local draft must never block the practice workspace.
    }

    const hydrationTimer = window.setTimeout(() => {
      if (restoredJourney) setJourney(restoredJourney);
      setHydrated(true);
    }, 0);

    return () => window.clearTimeout(hydrationTimer);
  }, [storageKey]);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(storageKey, JSON.stringify(journey));
  }, [hydrated, journey, storageKey]);

  useEffect(() => {
    if (!hydrated) return;
    onFocusModeChange?.(journey.focusMode);
  }, [hydrated, journey.focusMode, onFocusModeChange]);

  const activeIndex = STAGES.findIndex((stage) => stage.id === journey.activeStage);
  const completedCount = journey.completed.length;
  const progressLabel = `${completedCount} of ${STAGES.length} stages signed off`;
  const nextStage = STAGES[activeIndex + 1];

  function selectStage(stage: LearningStage) {
    setShowNudge(false);
    setJourney((current) => ({ ...current, activeStage: stage }));
  }

  function completeActiveStage() {
    setJourney((current) => {
      const completed = current.completed.includes(current.activeStage)
        ? current.completed
        : [...current.completed, current.activeStage];
      const currentIndex = STAGE_IDS.indexOf(current.activeStage);
      const next = STAGE_IDS[currentIndex + 1] ?? current.activeStage;
      return { ...current, completed, activeStage: next };
    });
    setShowNudge(false);
  }

  function renderStageContent() {
    switch (journey.activeStage) {
      case "study":
        return (
          <div className={styles.stageBody}>
            <p>
              Read the problem once for meaning before you optimize. Keep the target outcome
              visible while you work.
            </p>
            {learningObjectives.length > 0 && (
              <ul>
                {learningObjectives.slice(0, 3).map((objective) => (
                  <li key={objective}>{objective}</li>
                ))}
              </ul>
            )}
          </div>
        );
      case "discover":
        return (
          <div className={styles.stageBody}>
            <p>Find the boundaries that should shape your approach.</p>
            {constraints.length > 0 ? (
              <ul>
                {constraints.slice(0, 4).map((constraint) => (
                  <li key={constraint}>{constraint}</li>
                ))}
              </ul>
            ) : (
              <p className={styles.muted}>No additional public constraints are listed.</p>
            )}
          </div>
        );
      case "practice":
        return (
          <div className={styles.stageBody}>
            <label className={styles.reflectionLabel} htmlFor={`practice-reflection-${slug}`}>
              Explain your planned approach and complexity in your own words.
            </label>
            <textarea
              id={`practice-reflection-${slug}`}
              onChange={(event) =>
                setJourney((current) => ({ ...current, reflection: event.target.value }))
              }
              placeholder="I plan to use… because… Expected time is O(…), space is O(…)."
              value={journey.reflection}
            />
            <small>Saved in this browser as you type.</small>
          </div>
        );
      case "create":
        return (
          <div className={styles.stageBody}>
            <p>
              Build the solution in the editor, then use public tests as feedback. Stage signoff
              is only a learning note; Run and Submit remain governed by the existing secure
              execution and evaluation flow.
            </p>
          </div>
        );
      case "challenge":
        return (
          <div className={styles.stageBody}>
            <p>
              Stretch the solution beyond the happy path: what changes with much larger input,
              streaming data, stricter latency, or a different memory budget?
            </p>
            <p className={styles.challengePrompt}>
              Name one assumption you would revisit and one trade-off you would make.
            </p>
          </div>
        );
    }
  }

  const practiceNeedsReflection =
    journey.activeStage === "practice" && journey.reflection.trim().length < 20;

  return (
    <section aria-label="Guided practice journey" className={styles.root}>
      <div className={styles.topline}>
        <div>
          <span className={styles.eyebrow}>GUIDED PRACTICE</span>
          <strong>One clear next step, without racing the clock.</strong>
          <small>{progressLabel}</small>
        </div>
        <button
          aria-pressed={journey.focusMode}
          className={styles.focusButton}
          onClick={() =>
            setJourney((current) => ({ ...current, focusMode: !current.focusMode }))
          }
          type="button"
        >
          {journey.focusMode ? <Eye size={15} /> : <EyeOff size={15} />}
          {journey.focusMode ? "Show timer" : "Hide timer"}
        </button>
      </div>

      <div className={styles.progressTrack} aria-hidden="true">
        <span style={{ width: `${(completedCount / STAGES.length) * 100}%` }} />
      </div>

      <div className={styles.stageTabs} role="tablist" aria-label="Learning stages">
        {STAGES.map((stage, index) => {
          const Icon = stage.icon;
          const complete = journey.completed.includes(stage.id);
          const active = stage.id === journey.activeStage;
          return (
            <button
              aria-selected={active}
              className={`${styles.stageTab} ${active ? styles.stageTabActive : ""}`}
              key={stage.id}
              onClick={() => selectStage(stage.id)}
              role="tab"
              type="button"
            >
              <span className={complete ? styles.stageIconComplete : styles.stageIcon}>
                {complete ? <Check size={14} /> : <Icon size={14} />}
              </span>
              <span>
                <strong>{index + 1}. {stage.label}</strong>
                <small>{stage.caption}</small>
              </span>
            </button>
          );
        })}
      </div>

      <div className={styles.activeCard}>
        <div className={styles.activeHeading}>
          <div>
            <span>STEP {activeIndex + 1}</span>
            <h3>{STAGES[activeIndex]?.label}</h3>
          </div>
          {nextStage && <small>Next suggested: {nextStage.label}</small>}
        </div>

        {renderStageContent()}

        <div className={styles.actions}>
          <button
            className={styles.nudgeButton}
            onClick={() => setShowNudge((current) => !current)}
            type="button"
          >
            <Lightbulb size={15} /> {showNudge ? "Hide guided nudge" : "Show guided nudge"}
          </button>
          <button
            className={styles.completeButton}
            disabled={practiceNeedsReflection}
            onClick={completeActiveStage}
            type="button"
          >
            <Check size={15} /> Mark this step complete
          </button>
        </div>

        {showNudge && (
          <div className={styles.nudge}>
            <Lightbulb size={16} />
            <div>
              <strong>Guided nudge</strong>
              <p>{NUDGES[journey.activeStage]}</p>
              <small>Using support never changes your score.</small>
            </div>
          </div>
        )}
        {practiceNeedsReflection && (
          <small className={styles.reflectionHint}>
            Write a short explanation before signing off this step.
          </small>
        )}
      </div>
    </section>
  );
}
