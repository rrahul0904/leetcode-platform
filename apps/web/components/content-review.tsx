"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Send,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { useState } from "react";

import {
  EmptyState,
  ErrorState,
  EvidenceNote,
  LoadingState,
  PageHeader,
} from "@/components/page-ui";
import {
  assignReviewer,
  decideReview,
  getReviewQueue,
  publishQuestion,
  transitionQuestion,
  type ReviewKind,
  type ReviewOutcome,
  type ReviewQueueItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCaseSlug } from "@/lib/product-data";

const localReviewers = {
  technical: "local-technical-reviewer",
  editorial: "local-editorial-reviewer",
} as const;

export function ContentReview() {
  const { principal } = useAuth();
  const queryClient = useQueryClient();
  const queue = useQuery({
    queryKey: ["review-queue"],
    queryFn: ({ signal }) => getReviewQueue(signal),
    retry: false,
  });
  const [reason, setReason] = useState(
    "I reviewed the package evidence and recorded this decision independently.",
  );
  const [notice, setNotice] = useState("");
  const permissions = new Set(principal?.permissions ?? []);

  const action = useMutation({
    mutationFn: async (work: () => Promise<{ message: string }>) => work(),
    onSuccess: async (result) => {
      setNotice(result.message);
      await queryClient.invalidateQueries({ queryKey: ["review-queue"] });
    },
    onError: () =>
      setNotice(
        "The server rejected this transition. Check role, assignment, state, and review independence.",
      ),
  });

  if (queue.isLoading)
    return (
      <div className="page-content">
        <LoadingState label="Loading the durable review queue" />
      </div>
    );

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="CONTENT OPERATIONS"
        title="Move validated versions through independent review."
        description="Assignments, decisions, comments, publication, deprecation, and audit records are persisted in PostgreSQL and enforced by backend roles."
      />
      <EvidenceNote>
        <strong>Separation of duties is active.</strong>
        <span>
          Authors cannot approve their own version, technical and editorial
          reviewers must differ, and only administrators can publish.
        </span>
      </EvidenceNote>
      {notice && (
        <div className="assignment-ready">
          <ShieldCheck size={20} />
          <div>
            <strong>Workflow update</strong>
            <p>{notice}</p>
          </div>
        </div>
      )}
      {queue.isError && <ErrorState retry={() => void queue.refetch()} />}
      {queue.data?.length === 0 && (
        <EmptyState
          title="The review queue is empty."
          description="Synchronize an automated-validation-complete package to create a reviewable version."
        />
      )}
      <section className="review-layout section-block">
        <div className="panel panel--wide">
          <div className="review-toolbar">
            <div>
              <span className="eyebrow">DURABLE QUEUE</span>
              <h2>{queue.data?.length ?? 0} content versions</h2>
            </div>
          </div>
          <div className="roster-list">
            {queue.data?.map((item) => (
              <ReviewRow
                key={item.question_version_id}
                item={item}
                canAssign={permissions.has("review:assign")}
                canTechnical={permissions.has("review:technical")}
                canEditorial={permissions.has("review:editorial")}
                canPublish={permissions.has("content:publish")}
                reason={reason}
                setReason={setReason}
                busy={action.isPending}
                run={(work) => action.mutate(work)}
              />
            ))}
          </div>
        </div>
        <aside className="panel">
          <span className="eyebrow">SIGNED-IN AUTHORITY</span>
          <h2>{principal?.display_name}</h2>
          <div className="skill-row">
            {principal?.roles.map((role) => (
              <span key={role}>{role}</span>
            ))}
          </div>
          <ol className="state-machine">
            <li className="done">
              <CheckCircle2 size={15} />
              <span>Automated validation</span>
            </li>
            <li className="current">
              <CircleDot size={15} />
              <span>Technical review</span>
            </li>
            <li>
              <span>Editorial review</span>
            </li>
            <li>
              <span>Approved</span>
            </li>
            <li>
              <span>Published</span>
            </li>
          </ol>
          {!permissions.has("review:read") && (
            <div className="inline-alert">
              <AlertTriangle size={17} />
              <span>This role cannot read the private review queue.</span>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}

function ReviewRow({
  item,
  canAssign,
  canTechnical,
  canEditorial,
  canPublish,
  reason,
  setReason,
  busy,
  run,
}: {
  item: ReviewQueueItem;
  canAssign: boolean;
  canTechnical: boolean;
  canEditorial: boolean;
  canPublish: boolean;
  reason: string;
  setReason: (value: string) => void;
  busy: boolean;
  run: (work: () => Promise<{ message: string }>) => void;
}) {
  const assignment = (kind: ReviewKind) =>
    item.assignments.find((value) => value.kind === kind);
  const decide = (kind: ReviewKind, outcome: ReviewOutcome) =>
    run(() => decideReview(item.question_version_id, kind, outcome, reason));
  return (
    <article className="review-row">
      <span className="review-row__state">
        <CircleDot size={14} /> {item.state.replaceAll("_", " ")}
      </span>
      <div>
        <span className="question-id">
          {item.external_id} · v{item.version}
        </span>
        <strong>{item.title}</strong>
        <small>
          Author: {item.author_subject_id} · validation:{" "}
          {item.validation_status ?? "missing"}
        </small>
        <small>
          Technical:{" "}
          {assignment("technical")?.reviewer_display_name ?? "unassigned"} ·
          Editorial:{" "}
          {assignment("editorial")?.reviewer_display_name ?? "unassigned"}
        </small>
        {(canTechnical || canEditorial) && (
          <label className="reviewer-form">
            <span>Decision comment</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
        )}
        <div className="skill-row">
          {canAssign && (
            <>
              <button
                className="button button--ghost"
                disabled={busy}
                onClick={() =>
                  run(() =>
                    assignReviewer(
                      item.question_version_id,
                      "technical",
                      localReviewers.technical,
                    ),
                  )
                }
              >
                <UserCheck size={14} /> Assign technical
              </button>
              <button
                className="button button--ghost"
                disabled={busy}
                onClick={() =>
                  run(() =>
                    assignReviewer(
                      item.question_version_id,
                      "editorial",
                      localReviewers.editorial,
                    ),
                  )
                }
              >
                <UserCheck size={14} /> Assign editorial
              </button>
            </>
          )}
          {canTechnical && item.state === "awaiting_technical_review" && (
            <DecisionButtons
              kind="technical"
              disabled={busy || reason.trim().length < 10}
              decide={decide}
            />
          )}
          {canEditorial && item.state === "awaiting_editorial_review" && (
            <DecisionButtons
              kind="editorial"
              disabled={busy || reason.trim().length < 10}
              decide={decide}
            />
          )}
          {canPublish && item.state === "approved" && (
            <button
              className="button button--primary"
              disabled={busy}
              onClick={() =>
                run(() => publishQuestion(item.question_version_id))
              }
            >
              <Send size={14} /> Publish
            </button>
          )}
          {canPublish && item.state === "published" && (
            <button
              className="button button--ghost"
              disabled={busy}
              onClick={() =>
                run(() =>
                  transitionQuestion(item.question_version_id, "deprecated"),
                )
              }
            >
              Deprecate
            </button>
          )}
          {canPublish && item.state === "deprecated" && (
            <button
              className="button button--ghost"
              disabled={busy}
              onClick={() =>
                run(() =>
                  transitionQuestion(item.question_version_id, "archived"),
                )
              }
            >
              Archive
            </button>
          )}
        </div>
      </div>
      <span className="status-chip">{titleCaseSlug(item.state)}</span>
    </article>
  );
}

function DecisionButtons({
  kind,
  disabled,
  decide,
}: {
  kind: ReviewKind;
  disabled: boolean;
  decide: (kind: ReviewKind, outcome: ReviewOutcome) => void;
}) {
  return (
    <>
      <button
        className="button button--primary"
        disabled={disabled}
        onClick={() => decide(kind, "approved")}
      >
        <CheckCircle2 size={14} /> Approve
      </button>
      <button
        className="button button--ghost"
        disabled={disabled}
        onClick={() => decide(kind, "changes_requested")}
      >
        Request changes
      </button>
      <button
        className="button button--ghost"
        disabled={disabled}
        onClick={() => decide(kind, "rejected")}
      >
        Reject
      </button>
    </>
  );
}
