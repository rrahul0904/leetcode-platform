import {
  ArrowRight,
  BookOpen,
  CircleGauge,
  Clock3,
  MessageSquareText,
  Route,
  Target,
} from "lucide-react";
import Link from "next/link";

import { learningPaths, titleCaseSlug } from "@/lib/product-data";

import styles from "./learning-paths.module.css";

export function LearningPaths() {
  return (
    <section className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <Route size={14} /> LEARNING PATHS
          </span>
          <h1>Turn the question bank into a deliberate preparation plan.</h1>
          <p>
            Each path groups the canonical SkillForge tracks into a role-oriented sequence.
            Practice stays in the governed question bank, interviews stay in the persisted
            mock workspace, and readiness stays evidence-backed.
          </p>
        </div>
        <Link className={styles.readinessLink} href="/progress">
          <CircleGauge size={18} />
          <span>
            <strong>Check readiness</strong>
            <small>Use current evidence to decide what to practice next.</small>
          </span>
          <ArrowRight size={16} />
        </Link>
      </header>

      <div className={styles.grid}>
        {learningPaths.map((path) => {
          const primaryTrack = path.tracks[0];
          return (
            <article className={styles.card} key={path.id}>
              <div className={styles.cardTop}>
                <span>{path.role}</span>
                <div>
                  <Clock3 size={14} />
                  <small>{path.duration} · {path.hours}</small>
                </div>
              </div>

              <h2>{path.title}</h2>

              <div className={styles.tracks}>
                {path.tracks.map((track) => (
                  <span key={track}>{titleCaseSlug(track)}</span>
                ))}
              </div>

              <div className={styles.outcomes}>
                <span className={styles.sectionLabel}>Target outcomes</span>
                {path.outcomes.map((outcome) => (
                  <p key={outcome}>
                    <Target size={14} />
                    {outcome}
                  </p>
                ))}
              </div>

              <div className={styles.actions}>
                <Link
                  href={`/question-bank?track=${encodeURIComponent(primaryTrack)}`}
                >
                  <BookOpen size={15} />
                  Start focused practice
                </Link>
                <Link href="/mock-interviews">
                  <MessageSquareText size={15} />
                  Run a mock interview
                </Link>
              </div>
            </article>
          );
        })}
      </div>

      <section className={styles.boundary}>
        <div>
          <span className={styles.eyebrow}>HOW IT WORKS</span>
          <h2>One platform, shared evidence.</h2>
        </div>
        <p>
          Learning paths do not create a second curriculum database or a separate grading
          system. They organize existing SkillForge tracks and send candidates into the
          same published questions, execution evidence, tutor, mock-interview reports, and
          readiness model used everywhere else in the platform.
        </p>
      </section>
    </section>
  );
}
