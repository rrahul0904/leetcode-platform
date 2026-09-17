"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import {
  analyzeCareerJob,
  extractCareerResume,
  presignCareerResumeUpload,
  type CareerJobAnalysis,
  type CareerJobAnalysisInput,
  type CareerResumeDocument,
  uploadCareerResumeBinary,
} from "@/lib/career-api";

import styles from "./career-workspace.module.css";

const MAX_RESUME_BYTES = 8 * 1024 * 1024;
const PDF_MIME = "application/pdf";
const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

type ResumeMode = "upload" | "paste";
type ResumeUploadState = "idle" | "hashing" | "uploading" | "extracting" | "ready" | "failed";

const EMPTY_FORM: CareerJobAnalysisInput = {
  job_title: "",
  company: "",
  source_url: "",
  resume_text: "",
  job_description: "",
};

function resumeMimeType(file: File): string {
  const lowerName = file.name.toLowerCase();
  if (lowerName.endsWith(".pdf") && (!file.type || file.type === PDF_MIME)) {
    return PDF_MIME;
  }
  if (lowerName.endsWith(".docx") && (!file.type || file.type === DOCX_MIME)) {
    return DOCX_MIME;
  }
  throw new Error("Choose a PDF or DOCX resume with a matching file type.");
}

async function sha256(file: File): Promise<string> {
  const digest = await window.crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function uploadStateLabel(state: ResumeUploadState): string {
  switch (state) {
    case "hashing":
      return "Checking file integrity…";
    case "uploading":
      return "Uploading securely…";
    case "extracting":
      return "Extracting resume text…";
    case "ready":
      return "Resume ready";
    case "failed":
      return "Upload needs attention";
    default:
      return "PDF or DOCX · up to 8 MiB";
  }
}

export function CareerWorkspace() {
  const [form, setForm] = useState<CareerJobAnalysisInput>(EMPTY_FORM);
  const [analysis, setAnalysis] = useState<CareerJobAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resumeMode, setResumeMode] = useState<ResumeMode>("upload");
  const [resumeDocument, setResumeDocument] = useState<CareerResumeDocument | null>(null);
  const [resumeFileName, setResumeFileName] = useState<string | null>(null);
  const [resumeUploadState, setResumeUploadState] = useState<ResumeUploadState>("idle");
  const [resumeUploadError, setResumeUploadError] = useState<string | null>(null);

  const pastedResume = form.resume_text?.trim() ?? "";
  const resumeReady = resumeMode === "upload" ? resumeDocument !== null : pastedResume.length >= 40;
  const canAnalyze = resumeReady && form.job_description.trim().length >= 40;
  const resumeBusy = ["hashing", "uploading", "extracting"].includes(resumeUploadState);

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
        job_description: form.job_description.trim(),
        ...(resumeMode === "upload" && resumeDocument
          ? { document_id: resumeDocument.document_id }
          : { resume_text: pastedResume }),
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

  async function onResumeFile(file: File | undefined) {
    if (!file || resumeBusy) return;
    setResumeDocument(null);
    setResumeFileName(file.name);
    setResumeUploadError(null);
    setError(null);

    try {
      if (file.size <= 0) throw new Error("Resume file must not be empty.");
      if (file.size > MAX_RESUME_BYTES) throw new Error("Resume files are limited to 8 MiB.");
      const mimeType = resumeMimeType(file);

      setResumeUploadState("hashing");
      const checksumSha256 = await sha256(file);

      setResumeUploadState("uploading");
      const presigned = await presignCareerResumeUpload({
        fileName: file.name,
        mimeType,
        sizeBytes: file.size,
        checksumSha256,
      });
      await uploadCareerResumeBinary(presigned.upload_url, file, mimeType);

      setResumeUploadState("extracting");
      const document = await extractCareerResume(presigned.file_id);
      setResumeDocument(document);
      setResumeUploadState("ready");
    } catch (caught) {
      setResumeDocument(null);
      setResumeUploadState("failed");
      setResumeUploadError(
        caught instanceof Error ? caught.message : "CareerOS could not process this resume.",
      );
    }
  }

  function clearUploadedResume() {
    if (resumeBusy) return;
    setResumeDocument(null);
    setResumeFileName(null);
    setResumeUploadError(null);
    setResumeUploadState("idle");
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
            Upload or paste your resume and add the role you want. CareerOS maps evidence, exposes
            gaps, explains the fit score, and builds an interview pack you can take directly into
            SkillForge practice.
          </p>
        </div>
        <aside className={styles.heroNote}>
          <strong>Explainable and candidate-owned</strong>
          <span>
            Resume files stay in private object storage. CareerOS stores extracted text and uses a
            deterministic evidence score before any model-backed features are introduced.
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
              <span className={styles.fieldLabel}>Resume</span>
              <div className={styles.modeTabs} role="group" aria-label="Resume source">
                <button
                  className={resumeMode === "upload" ? styles.modeTabActive : styles.modeTab}
                  onClick={() => setResumeMode("upload")}
                  type="button"
                >
                  Upload PDF/DOCX
                </button>
                <button
                  className={resumeMode === "paste" ? styles.modeTabActive : styles.modeTab}
                  onClick={() => setResumeMode("paste")}
                  type="button"
                >
                  Paste text
                </button>
              </div>

              {resumeMode === "upload" ? (
                <div className={styles.uploadBox}>
                  <input
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    className={styles.fileInput}
                    disabled={resumeBusy}
                    id="career-resume-file"
                    onChange={(event) => void onResumeFile(event.target.files?.[0])}
                    type="file"
                  />
                  <label className={styles.filePicker} htmlFor="career-resume-file">
                    {resumeFileName ? "Replace resume" : "Choose resume"}
                  </label>
                  <div className={styles.uploadStatus} aria-live="polite">
                    <strong>{resumeFileName ?? "No file selected"}</strong>
                    <span>{uploadStateLabel(resumeUploadState)}</span>
                    {resumeDocument && (
                      <span>{resumeDocument.character_count.toLocaleString()} extracted characters</span>
                    )}
                  </div>
                  {resumeFileName && !resumeBusy && (
                    <button className={styles.textButton} onClick={clearUploadedResume} type="button">
                      Remove
                    </button>
                  )}
                  {resumeUploadError && <p className={styles.uploadError}>{resumeUploadError}</p>}
                </div>
              ) : (
                <textarea
                  id="career-resume"
                  value={form.resume_text ?? ""}
                  onChange={(event) => update("resume_text", event.target.value)}
                  placeholder="Paste your resume here. Include skills, projects, outcomes, and recent experience."
                />
              )}
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
            <span>
              {resumeMode === "upload"
                ? "Upload a text-bearing PDF/DOCX and add at least 40 characters of job description."
                : "Paste at least 40 characters of resume and job-description text."}
            </span>
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