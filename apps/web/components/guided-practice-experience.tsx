"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { GuidedPracticeJourney } from "@/components/guided-practice-journey";
import { SkillsForgePracticeWorkspace } from "@/components/skillsforge-practice-workspace";
import { TutorDock } from "@/components/tutor-dock";
import { getPublishedQuestion } from "@/lib/api";

import styles from "./guided-practice-experience.module.css";

export function GuidedPracticeExperience({ slug }: { slug: string }) {
  const [focusMode, setFocusMode] = useState(false);
  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });

  return (
    <>
      <div className={focusMode ? styles.focusExperience : undefined}>
        {question.data && (
          <div className={styles.guideContainer}>
            <GuidedPracticeJourney
              constraints={question.data.public_constraints}
              learningObjectives={question.data.learning_objectives}
              onFocusModeChange={setFocusMode}
              slug={slug}
            />
          </div>
        )}
        <SkillsForgePracticeWorkspace slug={slug} />
      </div>
      <TutorDock slug={slug} />
    </>
  );
}
