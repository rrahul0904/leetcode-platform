"use client";

import { useMutation } from "@tanstack/react-query";
import { Braces, CheckCircle2, FlaskConical, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import {
  runContentFactoryBatch,
  type ContentFactoryBatchInput,
  type ContentImportReport,
} from "@/lib/api";

export function ContentFactory() {
  const [questionsJson, setQuestionsJson] = useState("[]");
  const [promptVersion, setPromptVersion] = useState("factory-v1");
  const [provider, setProvider] = useState("human-directed");
  const [model, setModel] = useState("original-authoring-workflow");
  const [allowMixed, setAllowMixed] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [notice, setNotice] = useState("");
  const [report, setReport] = useState<ContentImportReport | null>(null);
  const factory = useMutation({
    mutationFn: (batch: ContentFactoryBatchInput) =>
      runContentFactoryBatch(batch),
    onSuccess: (result) => {
      setReport(result);
      setNotice(
        result.dry_run
          ? "Batch validated and traced without creating question versions."
          : "Accepted records were created as generated drafts; publication remains blocked pending review.",
      );
    },
    onError: (error) => setNotice(error.message),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const parsed: unknown = JSON.parse(questionsJson);
      const questions = Array.isArray(parsed) ? parsed : [parsed];
      factory.mutate({
        questions,
        prompt_version: promptVersion,
        model_provider: provider,
        model_identifier: model,
        allow_mixed_tracks: allowMixed,
        dry_run: dryRun,
      } as ContentFactoryBatchInput);
    } catch {
      setNotice(
        "Questions must be valid JSON: one object or an array of up to ten objects.",
      );
    }
  }
  return (
    <div className="page-content">
      <PageHeader
        eyebrow="CONTROLLED CONTENT FACTORY"
        title="Generate in small batches, then prove every package."
        description="Submit one to ten strict universal question objects. The same rights, duplicate, execution, rubric, difficulty, and security gates run before any draft is created."
      />
      <EvidenceNote>
        <strong>No automatic publication.</strong>
        <span>
          Single-track batches are the default. Every item receives a durable
          provider, model, prompt, input/output hash, and validation trace.
        </span>
      </EvidenceNote>
      {notice && (
        <div className="assignment-ready">
          <ShieldCheck size={20} />
          <div>
            <strong>Factory result</strong>
            <p>{notice}</p>
          </div>
        </div>
      )}
      <section className="reviewer-layout section-block">
        <form className="panel reviewer-form" onSubmit={submit}>
          <SectionHeading
            eyebrow="BATCH INPUT"
            title="Universal question JSON"
          />
          <label>
            <span>Question object or array (maximum 10)</span>
            <textarea
              value={questionsJson}
              onChange={(event) => setQuestionsJson(event.target.value)}
              spellCheck={false}
            />
          </label>
          <label>
            <span>Prompt version</span>
            <input
              value={promptVersion}
              onChange={(event) => setPromptVersion(event.target.value)}
            />
          </label>
          <label>
            <span>Provider</span>
            <input
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            />
          </label>
          <label>
            <span>Model or workflow identifier</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
            />
          </label>
          <label>
            <span>
              <input
                type="checkbox"
                checked={allowMixed}
                onChange={(event) => setAllowMixed(event.target.checked)}
              />{" "}
              Explicitly allow mixed primary tracks
            </span>
          </label>
          <label>
            <span>
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(event) => setDryRun(event.target.checked)}
              />{" "}
              Dry-run validation first
            </span>
          </label>
          <button
            className="button button--primary"
            disabled={factory.isPending}
          >
            <FlaskConical size={15} /> Run controlled batch
          </button>
        </form>
        <div className="panel panel--wide">
          <SectionHeading
            eyebrow="BATCH REPORT"
            title={
              report
                ? `${report.accepted_count} accepted · ${report.rejected_count} rejected`
                : "Awaiting a batch"
            }
          />
          {!report && (
            <div className="mini-empty">
              <Braces size={28} />
              <strong>Validated results and traces appear here.</strong>
            </div>
          )}
          <div className="check-grid">
            {report?.items.map((item) => (
              <article
                className="check-card check-card--pass"
                key={item.ordinal}
              >
                <CheckCircle2 size={19} />
                <div>
                  <strong>{item.external_id ?? item.source_path}</strong>
                  <p>
                    {item.errors[0] ??
                      item.warnings[0] ??
                      "All required gates passed."}
                  </p>
                  <span>
                    {
                      item.stages.filter((stage) => stage.status === "passed")
                        .length
                    }{" "}
                    stages passed
                  </span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
