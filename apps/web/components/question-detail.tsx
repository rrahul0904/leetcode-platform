"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  BookOpenCheck,
  Building2,
  Clock3,
  Pencil,
  Save,
  ShieldCheck,
  Target,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-ui";
import { getPublishedQuestion } from "@/lib/api";
import { getExecutionCapability } from "@/lib/execution-capability";
import { titleCaseSlug } from "@/lib/product-data";
import {
  bookmarkQuestion,
  createQuestionNote,
  deleteQuestionNote,
  getQuestionEngagement,
  removeQuestionBookmark,
  updateQuestionNote,
} from "@/lib/question-engagement-client";

function runtimeLabel(runtime: "python3.13" | "postgresql18" | null) {
  if (runtime === "python3.13") return "Python 3.13";
  if (runtime === "postgresql18") return "PostgreSQL 18";
  return "Not executable";
}

export function QuestionDetail({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const [newNote, setNewNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingBody, setEditingBody] = useState("");

  const question = useQuery({
    queryKey: ["published-question", slug],
    queryFn: ({ signal }) => getPublishedQuestion(slug, signal),
  });
  const capability = useQuery({
    queryKey: ["execution-capability", slug],
    queryFn: ({ signal }) => getExecutionCapability(slug, signal),
  });
  const engagement = useQuery({
    queryKey: ["question-engagement", slug],
    queryFn: ({ signal }) => getQuestionEngagement(slug, signal),
  });

  const refreshEngagement = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["question-engagement", slug] }),
      queryClient.invalidateQueries({ queryKey: ["candidate-bookmarks"] }),
    ]);
  };

  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      if (engagement.data?.bookmarked) {
        await removeQuestionBookmark(slug);
        return;
      }
      await bookmarkQuestion(slug);
    },
    onSuccess: refreshEngagement,
  });

  const createNoteMutation = useMutation({
    mutationFn: (body: string) => createQuestionNote(slug, body),
    onSuccess: async () => {
      setNewNote("");
      await refreshEngagement();
    },
  });

  const updateNoteMutation = useMutation({
    mutationFn: ({ noteId, body }: { noteId: string; body: string }) =>
      updateQuestionNote(slug, noteId, body),
    onSuccess: async () => {
      setEditingNoteId(null);
      setEditingBody("");
      await refreshEngagement();
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: string) => deleteQuestionNote(slug, noteId),
    onSuccess: refreshEngagement,
  });

  if (question.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Loading published question" />
      </div>
    );
  }
  if (question.isError || !question.data) {
    return (
      <div className="page-content">
        <ErrorState retry={() => void question.refetch()} />
      </div>
    );
  }

  const item = question.data;
  const canPractice = capability.data?.availability === "runnable";
  const noteBusy =
    createNoteMutation.isPending ||
    updateNoteMutation.isPending ||
    deleteNoteMutation.isPending;

  return (
    <div className="page-content">
      <Link className="back-link" href="/question-bank">
        <ArrowLeft size={15} /> Back to question bank
      </Link>
      <section className="detail-hero">
        <div>
          <div className="question-card__topline">
            <span className="question-id">
              {item.external_id} · Version {item.publication_version}
            </span>
            <span className={`difficulty difficulty--${item.difficulty}`}>
              {item.difficulty}
            </span>
          </div>
          <h1>{item.title}</h1>
          <p>{item.learning_objectives[0]}</p>
          <div className="skill-row skill-row--large">
            {item.skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
          <div className="detail-actions">
            {canPractice && (
              <Link className="button button--primary" href={`/practice/${slug}`}>
                Start practice <ArrowRight size={16} />
              </Link>
            )}
            <button
              className="button button--secondary"
              type="button"
              aria-pressed={engagement.data?.bookmarked ?? false}
              disabled={engagement.isLoading || bookmarkMutation.isPending}
              onClick={() => bookmarkMutation.mutate()}
            >
              {engagement.data?.bookmarked ? (
                <BookmarkCheck size={16} />
              ) : (
                <Bookmark size={16} />
              )}
              {bookmarkMutation.isPending
                ? "Saving…"
                : engagement.data?.bookmarked
                  ? "Bookmarked"
                  : "Bookmark"}
            </button>
            <Link
              className="button button--secondary"
              href={`/question-bank/${slug}/solution`}
            >
              <BookOpenCheck size={16} /> Review solution
            </Link>
          </div>
          {bookmarkMutation.isError && (
            <p className="boundary-note" role="alert">
              Bookmark could not be saved. Your existing database state was not changed.
            </p>
          )}
          {capability.isLoading && (
            <p className="boundary-note">Checking isolated execution availability…</p>
          )}
          {capability.isError && (
            <p className="boundary-note">
              Execution availability could not be verified. Practice is disabled until
              the backend capability check succeeds.
            </p>
          )}
          {capability.data?.availability === "hosted" && (
            <p className="boundary-note">
              {capability.data.reason ??
                "This published question is currently available for guided study only."}
            </p>
          )}
        </div>
        <aside className="availability-card">
          <ShieldCheck size={22} />
          <span>EXECUTION</span>
          <strong>
            {capability.data?.availability === "runnable"
              ? "Runnable"
              : capability.isLoading
                ? "Checking"
                : "Hosted study"}
          </strong>
          <p>
            {capability.data
              ? `${runtimeLabel(capability.data.runtime)} · ${capability.data.public_test_count} public · ${capability.data.hidden_test_count} hidden tests`
              : "The server decides whether this exact published version can execute."}
          </p>
          <Link href="/quality-gates">View the release gates</Link>
        </aside>
      </section>

      <section className="detail-grid section-block">
        <div className="panel panel--wide">
          <span className="eyebrow">PROBLEM</span>
          <h2>Candidate prompt</h2>
          <p className="lead-copy">{item.problem_statement}</p>
          <h3>Instructions</h3>
          <ul>
            {item.candidate_instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ul>
          <h3>Public constraints</h3>
          <ul>
            {item.public_constraints.map((constraint) => (
              <li key={constraint}>{constraint}</li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <span className="eyebrow">INTERVIEW SHAPE</span>
          <dl className="metadata-list">
            <div>
              <dt>
                <Clock3 size={15} /> Duration
              </dt>
              <dd>{item.estimated_duration_minutes} minutes</dd>
            </div>
            <div>
              <dt>
                <Target size={15} /> Track
              </dt>
              <dd>{titleCaseSlug(item.track)}</dd>
            </div>
            <div>
              <dt>
                <Users size={15} /> Expected level
              </dt>
              <dd>{titleCaseSlug(item.role_level)}</dd>
            </div>
            <div>
              <dt>
                <Building2 size={15} /> Style relevance
              </dt>
              <dd>
                {item.company_style_tags.map(titleCaseSlug).join(", ") ||
                  "General interview"}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="panel section-block" aria-labelledby="question-notes-title">
        <span className="eyebrow">PRIVATE NOTES</span>
        <h2 id="question-notes-title">Your notes</h2>
        <p>
          Notes are private to your SkillsForge AI account and persist across sessions.
        </p>
        {engagement.isLoading && <LoadingState label="Loading your question notes" />}
        {engagement.isError && (
          <div className="boundary-note" role="alert">
            <strong>Notes are unavailable right now.</strong>
            <button
              className="text-link"
              type="button"
              onClick={() => void engagement.refetch()}
            >
              Retry
            </button>
          </div>
        )}
        {engagement.data && (
          <>
            <label>
              <span>Add a private note</span>
              <textarea
                value={newNote}
                maxLength={10_000}
                onChange={(event) => setNewNote(event.target.value)}
                placeholder="Capture the approach, edge cases, or a reminder for next time."
              />
            </label>
            <button
              className="button button--secondary"
              type="button"
              disabled={!newNote.trim() || noteBusy}
              onClick={() => createNoteMutation.mutate(newNote.trim())}
            >
              <Save size={15} /> {createNoteMutation.isPending ? "Saving…" : "Save note"}
            </button>
            {(createNoteMutation.isError ||
              updateNoteMutation.isError ||
              deleteNoteMutation.isError) && (
              <p className="boundary-note" role="alert">
                The note change could not be saved. Retry before leaving this page.
              </p>
            )}
            <div className="section-block" aria-live="polite">
              {engagement.data.notes.length === 0 ? (
                <p>No private notes yet.</p>
              ) : (
                engagement.data.notes.map((note) => (
                  <article className="boundary-note" key={note.id}>
                    {editingNoteId === note.id ? (
                      <>
                        <label>
                          <span>Edit note</span>
                          <textarea
                            value={editingBody}
                            maxLength={10_000}
                            onChange={(event) => setEditingBody(event.target.value)}
                          />
                        </label>
                        <div className="detail-actions">
                          <button
                            className="button button--secondary"
                            type="button"
                            disabled={!editingBody.trim() || noteBusy}
                            onClick={() =>
                              updateNoteMutation.mutate({
                                noteId: note.id,
                                body: editingBody.trim(),
                              })
                            }
                          >
                            <Save size={15} /> Save changes
                          </button>
                          <button
                            className="button button--ghost"
                            type="button"
                            disabled={noteBusy}
                            onClick={() => {
                              setEditingNoteId(null);
                              setEditingBody("");
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <p>{note.body}</p>
                        <small>
                          Updated {new Date(note.updated_at).toLocaleString()}
                        </small>
                        <div className="detail-actions">
                          <button
                            className="button button--ghost"
                            type="button"
                            disabled={noteBusy}
                            aria-label="Edit note"
                            onClick={() => {
                              setEditingNoteId(note.id);
                              setEditingBody(note.body);
                            }}
                          >
                            <Pencil size={14} /> Edit
                          </button>
                          <button
                            className="button button--ghost"
                            type="button"
                            disabled={noteBusy}
                            aria-label="Delete note"
                            onClick={() => deleteNoteMutation.mutate(note.id)}
                          >
                            <Trash2 size={14} /> Delete
                          </button>
                        </div>
                      </>
                    )}
                  </article>
                ))
              )}
            </div>
          </>
        )}
      </section>

      <section className="panel section-block">
        <span className="eyebrow">PUBLIC EXAMPLES</span>
        {item.public_examples.length === 0 ? (
          <p>No public examples were supplied for this discussion question.</p>
        ) : (
          item.public_examples.map((example) => (
            <div className="boundary-note" key={example.id}>
              <strong>{example.name}</strong>
              <pre>
                {JSON.stringify(
                  {
                    input: example.input,
                    expected_output: example.expected_output,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          ))
        )}
      </section>
      {item.starter_code && (
        <section className="panel section-block">
          <span className="eyebrow">STARTER CODE</span>
          <h2>Begin your implementation</h2>
          <pre className="starter-code">
            <code>{item.starter_code}</code>
          </pre>
        </section>
      )}
    </div>
  );
}
