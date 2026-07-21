"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileArchive,
  RotateCcw,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { type DragEvent, type FormEvent, useState } from "react";

import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  LoadingState,
  PageHeader,
  SectionHeading,
} from "@/components/page-ui";
import {
  getContentImports,
  rollbackContentImport,
  uploadContentImport,
  type ContentImportReport,
} from "@/lib/api";

export function ContentImports() {
  const queryClient = useQueryClient();
  const history = useQuery({
    queryKey: ["content-imports"],
    queryFn: ({ signal }) => getContentImports(signal),
    retry: false,
  });
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [visibility, setVisibility] = useState<"public" | "private">("public");
  const [report, setReport] = useState<ContentImportReport | null>(null);
  const [notice, setNotice] = useState("");
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Select a file");
      return uploadContentImport(file, { dryRun, visibility });
    },
    onSuccess: async (result) => {
      setReport(result);
      setNotice(
        result.dry_run
          ? "Dry-run validation completed; no question versions were created."
          : "Import completed and accepted records entered a non-published draft state.",
      );
      await queryClient.invalidateQueries({ queryKey: ["content-imports"] });
    },
    onError: () =>
      setNotice("The upload was rejected by file-safety or import validation."),
  });
  const rollback = useMutation({
    mutationFn: (importId: string) => rollbackContentImport(importId),
    onSuccess: async (result) => {
      setNotice(
        `Rolled back ${result.rolled_back_versions} unreviewed versions.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["content-imports"] });
    },
    onError: () =>
      setNotice(
        "Rollback was rejected because the import is dry-run, already rolled back, or contains reviewed content.",
      ),
  });
  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setFile(event.dataTransfer.files[0] ?? null);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    upload.mutate();
  }
  function downloadRejections() {
    if (!report) return;
    const payload = JSON.stringify(
      report.items.filter((item) => item.errors.length),
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([payload], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `content-import-${report.import_id}-rejections.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (history.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Loading content import history" />
      </div>
    );
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="UNIVERSAL CONTENT INGESTION"
        title="Validate rights, originality, execution, and structure before review."
        description="Upload strict JSON, JSONL, CSV metadata, or safe ZIP packages. Imported and generated content never publishes automatically."
      />
      <EvidenceNote>
        <strong>Authorized content only.</strong>
        <span>
          Original, organization-owned, open-license, or partner-licensed
          evidence is mandatory. Restricted third-party content is quarantined
          or rejected.
        </span>
      </EvidenceNote>
      {notice && (
        <div className="assignment-ready">
          <ShieldCheck size={20} />
          <div>
            <strong>Import result</strong>
            <p>{notice}</p>
          </div>
        </div>
      )}
      <section className="reviewer-layout section-block">
        <div className="panel">
          <SectionHeading eyebrow="UPLOAD" title="Start an import" />
          <form className="reviewer-form" onSubmit={submit}>
            <div
              className="mini-empty"
              onDragOver={(event) => event.preventDefault()}
              onDrop={onDrop}
            >
              <UploadCloud size={28} />
              <strong>
                {file?.name ?? "Drop .json, .jsonl, .csv, or .zip"}
              </strong>
              <input
                aria-label="Content package file"
                type="file"
                accept=".json,.jsonl,.csv,.zip"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <label>
              <span>Visibility</span>
              <select
                value={visibility}
                onChange={(event) =>
                  setVisibility(event.target.value as "public" | "private")
                }
              >
                <option value="public">Public after review</option>
                <option value="private">Enterprise private tenant</option>
              </select>
            </label>
            <label>
              <span>
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(event) => setDryRun(event.target.checked)}
                />{" "}
                Dry-run validation only
              </span>
            </label>
            <button
              className="button button--primary"
              disabled={!file || upload.isPending}
            >
              <FileArchive size={15} />{" "}
              {dryRun ? "Validate package" : "Import as draft"}
            </button>
          </form>
        </div>
        <div className="panel panel--wide">
          <SectionHeading
            eyebrow="LATEST MACHINE REPORT"
            title={
              report
                ? `${report.accepted_count} accepted · ${report.rejected_count} rejected`
                : "No import run in this session"
            }
            aside={
              report && (
                <span
                  className={`status-chip ${report.rejected_count ? "status-chip--attention" : ""}`}
                >
                  {report.status}
                </span>
              )
            }
          />
          {!report && (
            <EmptyState
              title="Upload a package to inspect every stage."
              description="File safety, strict schema, rights, references, similarity, execution, rubric, difficulty, and security each produce a result."
            />
          )}
          {report && (
            <>
              <div className="check-grid">
                {report.items.map((item) => (
                  <article
                    className={`check-card check-card--${item.status === "rejected" ? "attention" : "pass"}`}
                    key={item.ordinal}
                  >
                    {item.status === "rejected" ? (
                      <AlertTriangle size={19} />
                    ) : (
                      <CheckCircle2 size={19} />
                    )}
                    <div>
                      <strong>{item.external_id ?? item.source_path}</strong>
                      <p>
                        {item.errors[0] ??
                          item.warnings[0] ??
                          "All required stages passed."}
                      </p>
                      <span>
                        {
                          item.stages.filter(
                            (stage) => stage.status === "passed",
                          ).length
                        }{" "}
                        passed ·{" "}
                        {
                          item.stages.filter(
                            (stage) => stage.status === "failed",
                          ).length
                        }{" "}
                        failed
                      </span>
                    </div>
                  </article>
                ))}
              </div>
              {report.rejected_count > 0 && (
                <button
                  className="button button--ghost"
                  onClick={downloadRejections}
                >
                  <Download size={15} /> Download rejection report
                </button>
              )}
            </>
          )}
        </div>
      </section>
      <section className="panel section-block">
        <SectionHeading
          eyebrow="IMPORT HISTORY"
          title={`${history.data?.length ?? 0} durable runs`}
        />
        {history.isError && <ErrorState retry={() => void history.refetch()} />}
        <div className="roster-list">
          {history.data?.map((item) => (
            <article className="review-row" key={item.import_id}>
              <span className="review-row__state">{item.source_method}</span>
              <div>
                <span className="question-id">{item.import_id}</span>
                <strong>{item.source_filename}</strong>
                <small>
                  {item.question_count} records · {item.accepted_count} accepted
                  · {item.rejected_count} rejected · {item.warning_count}{" "}
                  warnings
                </small>
              </div>
              {item.rollback_available && (
                <button
                  className="button button--ghost"
                  disabled={rollback.isPending}
                  onClick={() => rollback.mutate(item.import_id)}
                >
                  <RotateCcw size={14} /> Roll back
                </button>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
