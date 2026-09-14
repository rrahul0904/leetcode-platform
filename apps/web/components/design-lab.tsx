"use client";

import {
  ArrowRight,
  Bot,
  Box,
  Download,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { designTemplates } from "@/lib/product-data";
import {
  appendTutorEvent,
  CandidateLevel,
  createWhiteboardTutorSession,
  listTutorEvents,
  listTutorSessions,
  sendTutorMessage,
  TutorSession,
  WhiteboardSnapshot,
} from "@/lib/tutor-api";

type DesignNode = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
};

type DesignEdge = {
  source: string;
  target: string;
  label: string;
};

type Workspace = {
  templateId: string;
  title: string;
  requirements: string;
  assumptions: string;
  nodes: DesignNode[];
  edges: DesignEdge[];
};

const storageKey = "rigor-design-lab-draft-v2";
const levels: CandidateLevel[] = ["junior", "mid", "senior", "staff", "manager"];

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function initialWorkspace(templateId: string = designTemplates[0].id): Workspace {
  const template = designTemplates.find((item) => item.id === templateId) ?? designTemplates[0];
  return {
    templateId: template.id,
    title: `Untitled ${template.title}`,
    requirements: "",
    assumptions: "",
    nodes: template.nodes.map((label, index) => ({
      id: `template-${index + 1}`,
      label,
      type: index === 0 ? "edge" : "service",
      x: 80 + (index % 4) * 190,
      y: 90 + Math.floor(index / 4) * 120,
    })),
    edges: template.nodes.slice(1).map((_, index) => ({
      source: `template-${index + 1}`,
      target: `template-${index + 2}`,
      label: "",
    })),
  };
}

function splitLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toSnapshot(workspace: Workspace): WhiteboardSnapshot {
  return {
    nodes: workspace.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.type,
      x: node.x,
      y: node.y,
    })),
    edges: workspace.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.label || null,
    })),
    requirements: splitLines(workspace.requirements),
    notes: splitLines(workspace.assumptions),
  };
}

function fromSnapshot(snapshot: WhiteboardSnapshot, fallback: Workspace): Workspace {
  return {
    ...fallback,
    nodes: snapshot.nodes.map((node, index) => ({
      id: node.id,
      label: node.label,
      type: node.kind ?? "service",
      x: node.x ?? 80 + (index % 4) * 190,
      y: node.y ?? 90 + Math.floor(index / 4) * 120,
    })),
    edges: snapshot.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.label ?? "",
    })),
    requirements: snapshot.requirements.join("\n"),
    assumptions: snapshot.notes.join("\n"),
  };
}

function parseSnapshot(payload: Record<string, unknown>): WhiteboardSnapshot | null {
  try {
    const serialized = JSON.stringify(payload);
    const parsed = JSON.parse(serialized) as WhiteboardSnapshot;
    if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
      return null;
    }
    return {
      nodes: parsed.nodes,
      edges: parsed.edges,
      requirements: Array.isArray(parsed.requirements) ? parsed.requirements : [],
      notes: Array.isArray(parsed.notes) ? parsed.notes : [],
    };
  } catch {
    return null;
  }
}

export function DesignLab() {
  const [workspace, setWorkspace] = useState<Workspace>(() => initialWorkspace());
  const [saved, setSaved] = useState(false);
  const [newNode, setNewNode] = useState("");
  const [edgeSource, setEdgeSource] = useState("");
  const [edgeTarget, setEdgeTarget] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");
  const [level, setLevel] = useState<CandidateLevel>("senior");
  const [session, setSession] = useState<TutorSession | null>(null);
  const [tutorPrompt, setTutorPrompt] = useState("");
  const [tutorReply, setTutorReply] = useState("");
  const [status, setStatus] = useState("Browser recovery enabled");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const remoteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restored = useRef(false);
  const lastRemoteSnapshot = useRef("");

  const activeTemplate =
    designTemplates.find((item) => item.id === workspace.templateId) ?? designTemplates[0];
  const snapshot = useMemo(() => toSnapshot(workspace), [workspace]);

  useEffect(() => {
    let frame = 0;
    const controller = new AbortController();

    async function restore() {
      let local = initialWorkspace();
      try {
        const stored = window.localStorage.getItem(storageKey);
        if (stored) {
          local = JSON.parse(stored) as Workspace;
          frame = window.requestAnimationFrame(() => setWorkspace(local));
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      }

      try {
        const sessions = await listTutorSessions(controller.signal);
        const active = sessions.find(
          (candidate) => candidate.surface === "whiteboard" && candidate.status === "active",
        );
        if (!active) {
          setStatus("Local draft restored. Start a session for account-backed persistence.");
          return;
        }
        setSession(active);
        setLevel(active.candidate_level);
        const events = await listTutorEvents(active.id, controller.signal);
        const latest = [...events]
          .reverse()
          .find((event) => event.event_type === "whiteboard.snapshot");
        if (latest) {
          const remote = parseSnapshot(latest.payload);
          if (remote) {
            const restoredWorkspace = fromSnapshot(remote, local);
            setWorkspace(restoredWorkspace);
            window.localStorage.setItem(storageKey, JSON.stringify(restoredWorkspace));
            lastRemoteSnapshot.current = JSON.stringify(remote);
          }
        }
        setStatus("Account-backed design session restored.");
      } catch (caught) {
        if (!controller.signal.aborted) {
          setStatus("Local draft restored. Sign in to enable account-backed persistence.");
          if (caught instanceof Error && !caught.message.includes("401")) {
            setError(caught.message);
          }
        }
      } finally {
        restored.current = true;
      }
    }

    void restore();
    return () => {
      controller.abort();
      window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    if (!restored.current || !session) {
      return;
    }
    const encoded = JSON.stringify(snapshot);
    if (encoded === lastRemoteSnapshot.current) {
      return;
    }
    if (remoteSaveTimer.current) {
      clearTimeout(remoteSaveTimer.current);
    }
    remoteSaveTimer.current = setTimeout(() => {
      void appendTutorEvent(session.id, {
        eventType: "whiteboard.snapshot",
        idempotencyKey: createId("whiteboard-autosave"),
        payload: snapshot,
      })
        .then(() => {
          lastRemoteSnapshot.current = encoded;
          setStatus("Autosaved to your design session.");
        })
        .catch((caught: unknown) => {
          setStatus("Local draft saved; remote autosave needs attention.");
          setError(caught instanceof Error ? caught.message : "Remote autosave failed");
        });
    }, 700);
    return () => {
      if (remoteSaveTimer.current) {
        clearTimeout(remoteSaveTimer.current);
      }
    };
  }, [session, snapshot]);

  function update(next: Workspace) {
    setWorkspace(next);
    window.localStorage.setItem(storageKey, JSON.stringify(next));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1000);
  }

  function chooseTemplate(templateId: string) {
    update(initialWorkspace(templateId));
  }

  function addNode() {
    const label = newNode.trim();
    if (!label) {
      return;
    }
    const index = workspace.nodes.length;
    update({
      ...workspace,
      nodes: [
        ...workspace.nodes,
        {
          id: createId("node"),
          label,
          type: "service",
          x: 80 + (index % 4) * 190,
          y: 90 + Math.floor(index / 4) * 120,
        },
      ],
    });
    setNewNode("");
  }

  function addEdge(event: FormEvent) {
    event.preventDefault();
    if (!edgeSource || !edgeTarget || edgeSource === edgeTarget) {
      return;
    }
    update({
      ...workspace,
      edges: [
        ...workspace.edges,
        { source: edgeSource, target: edgeTarget, label: edgeLabel.trim() },
      ],
    });
    setEdgeLabel("");
  }

  async function ensureSession() {
    if (session) {
      return session;
    }
    const created = await createWhiteboardTutorSession({
      candidateLevel: level,
      title: workspace.title || "System design lab",
    });
    setSession(created);
    return created;
  }

  async function saveRemote() {
    setBusy(true);
    setError(null);
    try {
      const active = await ensureSession();
      await appendTutorEvent(active.id, {
        eventType: "whiteboard.snapshot",
        idempotencyKey: createId("whiteboard-save"),
        payload: snapshot,
      });
      lastRemoteSnapshot.current = JSON.stringify(snapshot);
      setStatus("Board saved to your account-backed design session.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save design session");
    } finally {
      setBusy(false);
    }
  }

  async function askTutor(event: FormEvent) {
    event.preventDefault();
    const prompt = tutorPrompt.trim();
    if (!prompt) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const active = await ensureSession();
      await appendTutorEvent(active.id, {
        eventType: "whiteboard.snapshot",
        idempotencyKey: createId("whiteboard-before-coach"),
        payload: snapshot,
      });
      lastRemoteSnapshot.current = JSON.stringify(snapshot);
      const reply = await sendTutorMessage(active.id, prompt, createId("design-tutor"));
      setTutorReply(reply.reply);
      setTutorPrompt("");
      setStatus(`Tutor responded with a ${reply.intervention.kind.replaceAll("_", " ")} prompt.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Tutor request failed");
    } finally {
      setBusy(false);
    }
  }

  function exportWorkspace() {
    const blob = new Blob(
      [JSON.stringify({ exported_at: new Date().toISOString(), ...workspace }, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${workspace.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "rigor-design"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const nodeName = (id: string) => workspace.nodes.find((node) => node.id === id)?.label ?? id;

  return (
    <div className="page-content page-content--wide">
      <PageHeader
        eyebrow="DESIGN LAB"
        title="Make architecture reasoning inspectable."
        description="Build a structured system model, persist candidate-owned snapshots, and let the tutor challenge requirements, failure modes, bottlenecks, and trade-offs without reading screenshots."
        actions={
          <>
            <button className="button button--ghost" disabled={busy} onClick={() => void saveRemote()}>
              <Save size={15} /> {session ? "Save session" : "Start session"}
            </button>
            <button className="button button--dark" onClick={exportWorkspace}>
              <Download size={15} /> Export JSON
            </button>
          </>
        }
      />

      <EvidenceNote tone={error ? "warning" : "success"}>
        <strong>{saved ? "Draft saved locally." : status}</strong>
        <span>
          {session
            ? `Candidate-owned whiteboard session ${session.id.slice(0, 8)} is active.`
            : "Local recovery works without a session; authenticated persistence and tutor coaching are opt-in."}
        </span>
      </EvidenceNote>
      {error ? <p className="form-error">{error}</p> : null}

      <section className="design-layout section-block">
        <aside className="template-rail panel">
          <SectionHeading eyebrow="TEMPLATES" title="Starting frame" />
          {designTemplates.map((template) => (
            <button
              className={
                template.id === workspace.templateId
                  ? "template-option template-option--active"
                  : "template-option"
              }
              key={template.id}
              onClick={() => chooseTemplate(template.id)}
            >
              <Box size={17} />
              <span>
                <strong>{template.title}</strong>
                <small>{template.description}</small>
              </span>
            </button>
          ))}
          <button
            className="button button--ghost button--full"
            onClick={() => chooseTemplate(workspace.templateId)}
          >
            <RotateCcw size={15} /> Reset template
          </button>
          <label className="field-label">
            <span>Interview level</span>
            <select value={level} onChange={(event) => setLevel(event.target.value as CandidateLevel)}>
              {levels.map((candidateLevel) => (
                <option key={candidateLevel} value={candidateLevel}>
                  {candidateLevel.charAt(0).toUpperCase() + candidateLevel.slice(1)}
                </option>
              ))}
            </select>
          </label>
        </aside>

        <div className="design-workspace">
          <div className="design-toolbar">
            <label>
              <span>Document title</span>
              <input
                value={workspace.title}
                onChange={(event) => update({ ...workspace, title: event.target.value })}
              />
            </label>
            <span className="save-indicator">
              <Save size={14} /> {session ? "Autosave: account + local" : "Autosave: local"}
            </span>
          </div>

          <div className="architecture-canvas" aria-label={`${activeTemplate.title} component canvas`}>
            <div className="canvas-label">
              <span>{activeTemplate.title}</span>
              <small>
                Structured components + explicit edges · layout coordinates persist with the snapshot
              </small>
            </div>
            <div className="node-flow">
              {workspace.nodes.map((node) => (
                <div className="design-node" key={node.id}>
                  <span>{node.type}</span>
                  <strong
                    contentEditable
                    suppressContentEditableWarning
                    onBlur={(event) =>
                      update({
                        ...workspace,
                        nodes: workspace.nodes.map((item) =>
                          item.id === node.id
                            ? { ...item, label: event.currentTarget.textContent || item.label }
                            : item,
                        ),
                      })
                    }
                  >
                    {node.label}
                  </strong>
                  <button
                    aria-label={`Remove ${node.label}`}
                    onClick={() =>
                      update({
                        ...workspace,
                        nodes: workspace.nodes.filter((item) => item.id !== node.id),
                        edges: workspace.edges.filter(
                          (edge) => edge.source !== node.id && edge.target !== node.id,
                        ),
                      })
                    }
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>

            {workspace.edges.length ? (
              <div className="design-edge-list" aria-label="System connections">
                {workspace.edges.map((edge, index) => (
                  <span key={`${edge.source}-${edge.target}-${index}`}>
                    {nodeName(edge.source)} <ArrowRight size={12} /> {nodeName(edge.target)}
                    {edge.label ? ` · ${edge.label}` : ""}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="add-node">
              <input
                value={newNode}
                onChange={(event) => setNewNode(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    addNode();
                  }
                }}
                placeholder="Add a service, store, queue, or control"
              />
              <button className="button button--primary" onClick={addNode}>
                <Plus size={15} /> Add component
              </button>
            </div>

            <form className="design-connection-form" onSubmit={addEdge}>
              <select
                aria-label="Connection source"
                value={edgeSource}
                onChange={(event) => setEdgeSource(event.target.value)}
              >
                <option value="">Source component</option>
                {workspace.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Connection target"
                value={edgeTarget}
                onChange={(event) => setEdgeTarget(event.target.value)}
              >
                <option value="">Target component</option>
                {workspace.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label}
                  </option>
                ))}
              </select>
              <input
                aria-label="Connection label"
                value={edgeLabel}
                onChange={(event) => setEdgeLabel(event.target.value)}
                placeholder="HTTP, events, reads, writes…"
              />
              <button className="button button--secondary" type="submit">
                <ArrowRight size={14} /> Connect
              </button>
            </form>
          </div>

          <div className="design-notes">
            <label>
              <span>Requirements and success metrics</span>
              <textarea
                value={workspace.requirements}
                onChange={(event) => update({ ...workspace, requirements: event.target.value })}
                placeholder="One requirement per line: scale, latency, availability, consistency, privacy…"
              />
            </label>
            <label>
              <span>Assumptions, risks, and trade-offs</span>
              <textarea
                value={workspace.assumptions}
                onChange={(event) => update({ ...workspace, assumptions: event.target.value })}
                placeholder="One note per line: failure modes, ownership, migration constraints, rejected alternatives…"
              />
            </label>
          </div>

          <section className="panel design-tutor-panel">
            <div className="design-tutor-heading">
              <Bot size={20} />
              <div>
                <strong>Architecture tutor</strong>
                <small>Coaches from the latest persisted structured snapshot.</small>
              </div>
              <Sparkles size={16} />
            </div>
            {tutorReply ? <p className="design-tutor-reply">{tutorReply}</p> : null}
            <form className="design-tutor-form" onSubmit={askTutor}>
              <input
                aria-label="Ask architecture tutor"
                value={tutorPrompt}
                onChange={(event) => setTutorPrompt(event.target.value)}
                placeholder="Challenge my bottleneck, consistency choice, failure mode, or scaling plan…"
              />
              <button className="button button--dark" disabled={busy} type="submit">
                Ask tutor
              </button>
            </form>
          </section>
        </div>
      </section>
    </div>
  );
}
