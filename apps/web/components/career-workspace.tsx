"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import {
  analyzeCareerJob,
  type CareerJobAnalysis,
  type CareerJobAnalysisInput,
} from "@/lib/career-api";

import styles from "./career-workspace.module.css";

const EMPTY_FORM: CareerJobAnalysisInput = {
  job_title: "",
  company: "",
  source_url: "",
  resume_text: "",
  job_description: "",
};

export function CareerWorkspace() {
  const [form, setForm] = useState<CareerJobAnalysisInput>(EMPTY_FORM);
  const [analysis, setAnalysis] = useState<CareerJobAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canAnalyze =
    form.resume_text.trim().length >= 40 && form.job_description.trim().length >= 40;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canAnalyze || loading) return;

    setLoading(true);
    setError(null);
    try {
      const jobTitle = form.job_title?.trim();
      const company = form.company?.trim();
      const sourceUrl = form.source_url?.trim();
      const result = await analyzeCareerJob({
        resume_text: form.resume_text.trim(),
        job_description: form.job_description.trim(),
        ...(jobTitle ? { job_title: jobTitle } : {}),
        ...(company ? { company } : {}),
        ...(sourceUrl ? { source_url: sourceUrl } : {}),
      });
      setAnalysis(result);
      window.requestAnimationFrame(() => {
        document.getElementById("career-analysis")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "CareerOS could not analyze this job.");
    } finally {
      setLoading(false);
    }
  }

  function update<K extends keyof CareerJobAnalysisInput>(
    field: K,
    value: CareerJobAnalysisInput[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className={styles.workspace}>
      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>CareerOS · Job intelligence</p>
          <h1 className={styles.title}>Turn one job description into a preparation plan.</h1>
          <p className={styles.subtitle}>
            Paste your resume and the role you want. CareerOS maps evidence, exposes gaps,
            explains the fit score, and builds an interview pack you can take directly into
            SkillForge practice.
          </p>
        </div>
        <aside className={styles.heroNote}>
          <strong>Wave 1 · Explainable by design</strong>
          <span>
            The first scoring engine uses deterministic skill and language evidence. No hidden
            model judgment is required to understand why a score changed.
          </span>
        </aside>
      </section>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div>
            <h2>Analyze a target role</h2>
            <p>Resume evidence + job requirements → fit, gaps, and interview focus.</p>
          </div>
        </header>

        <form className={styles.form} onSubmit={onSubmit}>
          <div className={styles.metaGrid}>
            <div className={styles.field}>
              <label htmlFor="career-job-title">Job title</label>
              <input
                id="career-job-title"
                value={form.job_title ?? ""}
                onChange={(event) => update("job_title", event.target.value)}
                placeholder="Senior Data Platform Engineer"
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="career-company">Company</label>
              <input
                id="career-company"
                value={form.company ?? ""}
                onChange={(event) => update("company", event.target.value)}
                placeholder="Company name"
              />
            </div>
          </div>

          <div className={styles.textGrid}>
            <div className={styles.field}>
              <label htmlFor="career-resume">Resume text</label>
              <textarea
                id="career-resume"
                value={form.resume_text}
                onChange={(event) => update("resume_text", event.target.value)}
                placeholder="Paste your resume here. Include skills, projects, outcomes, and recent experience."
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="career-job-description">Job description</label>
              <textarea
                id="career-job-description"
                value={form.job_description}
                onChange={(event) => update("job_description", event.target.value)}
                placeholder="Paste the complete job description here."
              />
            </div>
          </div>

          <div className={styles.formFooter}>
            <span>Minimum 40 characters in both text fields. Your result is generated on demand.</span>
            <button className={styles.primaryButton} type="submit" disabled={!canAnalyze || loading}>
              {loading ? "Analyzing…" : "Analyze role"}
            </button>
          </div>
          {error && <p className={styles.error}>{error}</p>}
        </form>
      </section>

      {analysis && (
        <section className={styles.results} id="career-analysis" aria-live="polite">
          <div className={styles.resultHeader}>
            <div>
              <p className={styles.eyebrow}>CareerOS analysis</p>
              <h2>
                {analysis.job_title || "Target role"}
                {analysis.company ? ` · ${analysis.company}` : ""}
              </h2>
              <p>{analysis.scoring_explanation}</p>
            </div>
            <div className={styles.score} aria-label={`Fit score ${analysis.fit_score} out of 100`}>
              <strong>{analysis.fit_score}</strong>
              <span>fit / 100</span>
            </div>
          </div>

          <div className={styles.metricGrid}>
            <div className={styles.metric}>
              <span>Skill coverage</span>
              <strong>{analysis.skill_coverage}%</strong>
            </div>
            <div className={styles.metric}>
              <span>Job language overlap</span>
              <strong>{analysis.language_overlap}%</strong>
            </div>
            <div className={styles.metric}>
              <span>Interview prompts</span>
              <strong>{analysis.interview_questions.length}</strong>
            </div>
          </div>

          <div className={styles.splitGrid}>
            <article className={styles.section}>
              <h3>Evidence already on your resume</h3>
              <p className={styles.sectionIntro}>
                Skills CareerOS found in both your resume and this job description.
              </p>
              <div className={styles.chips}>
                {analysis.matched_skills.length ? (
                  analysis.matched_skills.map((skill) => (
                    <span className={styles.chip} key={skill}>
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className={styles.chip}>No explicit skill match yet</span>
                )}
              </div>
              <ul className={styles.list}>
                {analysis.strengths.map((strength) => (
                  <li key={strength}>{strength}</li>
                ))}
              </ul>
            </article>

            <article className={styles.section}>
              <h3>Gaps to resolve before applying</h3>
              <p className={styles.sectionIntro}>
                Named requirements that are not explicit in the resume you supplied.
              </p>
              <div className={styles.chips}>
                {analysis.missing_skills.length ? (
                  analysis.missing_skills.map((skill) => (
                    <span className={`${styles.chip} ${styles.chipGap}`} key={skill}>
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className={styles.chip}>No named-skill gap detected</span>
                )}
              </div>
              <ul className={styles.list}>
                {analysis.risks.map((risk) => (
                  <li key={risk}>{risk}</li>
                ))}
              </ul>
            </article>
          </div>

          <article className={styles.section}>
            <h3>Priority language from the job</h3>
            <p className={styles.sectionIntro}>
              High-frequency terms worth validating against the exact language in your accomplishments.
            </p>
            <div className={styles.chips}>
              {analysis.priority_keywords.map((keyword) => (
                <span className={styles.chip} key={keyword}>
                  {keyword}
                </span>
              ))}
            </div>
          </article>

          <article className={styles.section}>
            <h3>Tailored interview pack</h3>
            <p className={styles.sectionIntro}>
              Questions are built from your matched evidence, missing requirements, and the target role.
            </p>
            <div className={styles.questionList}>
              {analysis.interview_questions.map((item, index) => (
                <div className={styles.question} key={`${item.category}-${item.focus}-${index}`}>
                  <div className={styles.questionMeta}>
                    <span>{item.category}</span>
                    <span>·</span>
                    <span>{item.focus}</span>
                  </div>
                  <p>{item.question}</p>
                  <small>{item.coaching_note}</small>
                </div>
              ))}
            </div>
            <div className={styles.actions}>
              <Link href="/question-bank">Open question bank</Link>
              <Link href="/mock-interviews">Open mock interviews</Link>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}