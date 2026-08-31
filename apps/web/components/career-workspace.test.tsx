import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CareerWorkspace } from "./career-workspace";

const api = vi.hoisted(() => ({
  analyzeCareerJob: vi.fn(),
  extractCareerResume: vi.fn(),
  presignCareerResumeUpload: vi.fn(),
  uploadCareerResumeBinary: vi.fn(),
}));

vi.mock("@/lib/career-api", () => api);

const ANALYSIS = {
  job_title: "Backend Engineer",
  company: "Example Co",
  source_url: null,
  fit_score: 82,
  skill_coverage: 86,
  language_overlap: 71,
  matched_skills: ["Python", "PostgreSQL"],
  missing_skills: ["Kubernetes"],
  resume_skills: ["Python", "PostgreSQL"],
  priority_keywords: ["backend", "python"],
  strengths: ["Your resume contains direct evidence for Python."],
  risks: ["Kubernetes is not explicit in the resume."],
  interview_questions: [
    {
      category: "experience",
      focus: "Python",
      question: "Tell me about a Python system you owned.",
      coaching_note: "Use measurable impact.",
    },
  ],
  scoring_explanation: "Explainable deterministic score.",
  job_id: "job-1",
  document_id: "document-1",
  analysis_id: "analysis-1",
  status: "saved",
  scoring_version: "deterministic-v1",
  created_at: "2026-08-31T02:00:00Z",
} as const;

const JOB_DESCRIPTION =
  "Backend engineer role requiring Python, PostgreSQL, Kubernetes, reliable APIs, and system design.";

beforeEach(() => {
  vi.clearAllMocks();
  api.presignCareerResumeUpload.mockResolvedValue({
    file_id: "file-1",
    method: "PUT",
    upload_url: "https://example.invalid/private-upload",
    expires_seconds: 300,
    storage_key: "candidate/file-1/resume.pdf",
  });
  api.uploadCareerResumeBinary.mockResolvedValue(undefined);
  api.extractCareerResume.mockResolvedValue({
    document_id: "document-1",
    candidate_file_id: "file-1",
    file_name: "resume.pdf",
    mime_type: "application/pdf",
    extraction_method: "pdf_text",
    character_count: 1234,
    created_at: "2026-08-31T02:00:00Z",
  });
  api.analyzeCareerJob.mockResolvedValue(ANALYSIS);
  vi.spyOn(window.crypto.subtle, "digest").mockResolvedValue(new Uint8Array(32).buffer);
});

describe("CareerWorkspace resume ingestion", () => {
  it("uploads, extracts, and analyzes an uploaded resume by document id", async () => {
    render(<CareerWorkspace />);

    const file = new File(["resume"], "resume.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "arrayBuffer", {
      value: vi.fn().mockResolvedValue(new TextEncoder().encode("resume").buffer),
    });

    fireEvent.change(screen.getByLabelText("Choose resume"), {
      target: { files: [file] },
    });

    await waitFor(() => expect(screen.getByText("Resume ready")).toBeInTheDocument());
    expect(api.presignCareerResumeUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        fileName: "resume.pdf",
        mimeType: "application/pdf",
        sizeBytes: file.size,
      }),
    );
    expect(api.uploadCareerResumeBinary).toHaveBeenCalledWith(
      "https://example.invalid/private-upload",
      file,
      "application/pdf",
    );
    expect(api.extractCareerResume).toHaveBeenCalledWith("file-1");
    expect(screen.getByText("1,234 extracted characters")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Job description"), {
      target: { value: JOB_DESCRIPTION },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze role" }));

    await waitFor(() => expect(api.analyzeCareerJob).toHaveBeenCalledTimes(1));
    const request = api.analyzeCareerJob.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(request.document_id).toBe("document-1");
    expect(request.job_description).toBe(JOB_DESCRIPTION);
    expect(request).not.toHaveProperty("resume_text");
    expect(await screen.findByText("82")).toBeInTheDocument();
  });

  it("keeps pasted resume text as an independent fallback", async () => {
    render(<CareerWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "Paste text" }));
    fireEvent.change(screen.getByLabelText("Resume"), {
      target: {
        value:
          "Backend engineer with Python, PostgreSQL, Docker, AWS and production API ownership.",
      },
    });
    fireEvent.change(screen.getByLabelText("Job description"), {
      target: { value: JOB_DESCRIPTION },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze role" }));

    await waitFor(() => expect(api.analyzeCareerJob).toHaveBeenCalledTimes(1));
    const request = api.analyzeCareerJob.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(request.resume_text).toContain("Backend engineer with Python");
    expect(request).not.toHaveProperty("document_id");
    expect(api.presignCareerResumeUpload).not.toHaveBeenCalled();
  });

  it("rejects oversized resumes before creating an upload", async () => {
    render(<CareerWorkspace />);

    const file = new File(["x"], "resume.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "size", { value: 8 * 1024 * 1024 + 1 });
    fireEvent.change(screen.getByLabelText("Choose resume"), {
      target: { files: [file] },
    });

    expect(await screen.findByText("Resume files are limited to 8 MiB.")).toBeInTheDocument();
    expect(api.presignCareerResumeUpload).not.toHaveBeenCalled();
  });
});
