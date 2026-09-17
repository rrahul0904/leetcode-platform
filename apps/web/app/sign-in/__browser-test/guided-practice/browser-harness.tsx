"use client";

import { Timer } from "lucide-react";
import { useState } from "react";

import { GuidedPracticeJourney } from "@/components/guided-practice-journey";
import styles from "@/components/guided-practice-experience.module.css";

const learningObjectives = [
  "Choose a reliable aggregation strategy.",
  "Explain the complexity and correctness trade-offs before coding.",
];

const constraints = [
  "Handle duplicate events safely.",
  "Keep memory bounded as input volume grows.",
];

export function GuidedPracticeBrowserHarness() {
  const [focusMode, setFocusMode] = useState(false);

  return (
    <main data-testid="guided-practice-browser-harness">
      <div className={focusMode ? styles.focusExperience : undefined}>
        <div aria-label="Practice timer" className="practice-timer">
          <Timer aria-hidden="true" size={15} />
          <strong>00:42</strong>
        </div>
        <div className={styles.guideContainer}>
          <GuidedPracticeJourney
            constraints={constraints}
            learningObjectives={learningObjectives}
            onFocusModeChange={setFocusMode}
            slug="browser-guided-practice"
          />
        </div>
        <div data-testid="workspace-sentinel">Practice workspace remains mounted.</div>
      </div>
      <div data-testid="tutor-sentinel">Tutor dock remains mounted.</div>
    </main>
  );
}
