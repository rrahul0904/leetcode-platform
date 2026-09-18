"use client";

import { ArrowRight, Bot, Download, GripVertical, Plus, Save, Trash2 } from "lucide-react";
import type { FormEvent, PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { designTemplates } from "@/lib/product-data";
import {
  appendTutorEvent,
  type CandidateLevel,
  createWhiteboardTutorSession,
  listTutorEvents,
  listTutorSessions,
  sendTutorMessage,
  type TutorSession,
  type WhiteboardSnapshot,
} from "@/lib/tutor-api";

import styles from "./direct-design-lab.module.css";

type DesignNode = {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
};

type DesignEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

type Workspace = {
  templateId: string;
  title: string;
  requirements: string;
  notes: string;
  nodes: DesignNode[];
  edges: DesignEdge[];
};

type DragState = {
  id: string;
  offsetX: number;
  offsetY: number;
};

const STORAGE_KEY = "rigor-design-lab-draft-v3";
const NODE_WIDTH = 176;
const NODE_HEIGHT = 104;
const FALLBACK_STAGE_WIDTH = 980;
const FALLBACK_STAGE_HEIGHT = 560;
const levels: CandidateLevel[] = ["junior", "mid", "senior", "staff", "manager"];
const nodeKinds = ["client", "gateway", "service", "queue", "database", "cache", "stream", "storage", "model", "control"];

const quickPrompts = [
  {
    label: "Find bottleneck",
    prompt: "Find the bottleneck in this design. Ask me to quantify why it is the bottleneck.",
  },
  {
    label: "Probe failures",
    prompt: "Probe the most important failure mode in this design and ask how I would contain it.",
  },
  {
    label: "Challenge consistency",
    prompt: "Challenge my consistency and durability choices. Ask for the trade-off I am making.",
  },
  {
    label: "Scale 10×",
    prompt: "Assume traffic grows 10x. Ask which component fails first and what I would change.",
  },
] as const;

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function initialWorkspace(templateId: string = designTemplates[0].id): Workspace {
  const template = designTemplates.find((item) => item.id === templateId) ?? designTemplates[0];
  const nodes = template.nodes.map((label, index) => ({
    id: `template-${index + 1}`,
    label,
    kind: index === 0 ? "client" : index === template.nodes.length - 1 ? "database" : "service",
    x: 56 + (index % 2) * 290,
    y: 72 + Math.floor(index / 2) * 178,
  }));
  return {
    templateId: template.id,
    title: `Untitled ${template.title}`,
    requirements: "",
    notes: "",
    nodes,
    edges: template.nodes.slice(1).map((_, index) => ({
      id: `template-edge-${index + 1}`,
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
      kind: node.kind,
      x: node.x,
      y: node.y,
    })),
    edges: workspace.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.label || null,
    })),
    requirements: splitLines(workspace.requirements),
    notes: splitLines(workspace.notes),
  };
}

function fromSnapshot(snapshot: WhiteboardSnapshot, fallback: Workspace): Workspace {
  const nodes = snapshot.nodes.map((node, index) => ({
    id: node.id,
    label: node.label,
    kind: node.kind ?? "service",
    x: node.x ?? 56 + (index % 2) * 290,
    y: node.y ?? 72 + Math.floor(index / 2) * 178,
  }));
  return {
    ...fallback,
    nodes,
    edges: snapshot.edges
      .filter(
        (edge) =>
          nodes.some((node) => node.id === edge.source) &&
          nodes.some((node) => node.id === edge.target),
      )
      .map((edge, index) => ({
        id: `restored-edge-${index}-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.label ?? "",
      })),
    requirements: snapshot.requirements.join("\n"),
    notes: snapshot.notes.join("\n"),
  };
}

function parseSnapshot(payload: Record<string, unknown>): WhiteboardSnapshot | null {
  try {
    const parsed = JSON.parse(JSON.stringify(payload)) as WhiteboardSnapshot;
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

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

export function DirectDesignLab() {
  const [workspace, setWorkspace] = useState<Workspace>(() => initialWorkspace());
  const [session, setSession] = useState<TutorSession | null>(null);
  const [level, setLevel] = useState<CandidateLevel>("senior");
  const [status, setStatus] = useState("Browser recovery enabled.");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [edgeSource, setEdgeSource] = useState("");
  const [edgeTarget, setEdgeTarget] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");
  const [tutorPrompt, setTutorPrompt] = useState("");
  const [tutorReply, setTutorReply] = useState("");

  const stageRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const workspaceRef = useRef(workspace);
  const remoteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restored = useRef(false);
  const lastRemoteSnapshot = useRef("");

  const activeTemplate =
    designTemplates.find((item) => item.id === workspace.templateId) ?? designTemplates[0];
  const snapshot = useMemo(() => toSnapshot(workspace), [workspace]);

  useEffect(() => {
    workspaceRef.current = workspace;
  }, [workspace]);

  useEffect(() => {
    const controller = new AbortController();

    async function restore() {
      let recovered = initialWorkspace();
      try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
          recovered = JSON.parse(stored) as Workspace;
          setWorkspace(recovered);
          workspaceRef.current = recovered;
        }
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
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
            recovered = fromSnapshot(remote, recovered);
            setWorkspace(recovered);
            workspaceRef.current = recovered;
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(recovered));
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
    return () => controller.abort();
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
          setStatus("Autosaved to your account-backed design session.");
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

  function commitWorkspace(next: Workspace) {
    workspaceRef.current = next;
    setWorkspace(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function setTransientWorkspace(next: Workspace) {
    workspaceRef.current = next;
    setWorkspace(next);
  }

  function chooseTemplate(templateId: string) {
    commitWorkspace(initialWorkspace(templateId));
    setEdgeSource("");
    setEdgeTarget("");
    setTutorReply("");
    setStatus("Template loaded and saved locally.");
  }

  function beginDrag(event: ReactPointerEvent<HTMLButtonElement>, node: DesignNode) {
    const stage = stageRef.current;
    if (!stage) {
      return;
    }
    const rect = stage.getBoundingClientRect();
    dragRef.current = {
      id: node.id,
      offsetX: event.clientX - rect.left - node.x,
      offsetY: event.clientY - rect.top - node.y,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function moveDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    const stage = stageRef.current;
    if (!drag || !stage) {
      return;
    }
    const rect = stage.getBoundingClientRect();
    const width = rect.width || FALLBACK_STAGE_WIDTH;
    const height = rect.height || FALLBACK_STAGE_HEIGHT;
    const x = clamp(event.clientX - rect.left - drag.offsetX, 8, width - NODE_WIDTH - 8);
    const y = clamp(event.clientY - rect.top - drag.offsetY, 8, height - NODE_HEIGHT - 8);
    const current = workspaceRef.current;
    setTransientWorkspace({
      ...current,
      nodes: current.nodes.map((node) => (node.id === drag.id ? { ...node, x, y } : node)),
    });
  }

  function finishDrag() {
    if (!dragRef.current) {
      return;
    }
    dragRef.current = null;
    const current = workspaceRef.current;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    setStatus(session ? "Position updated; account autosave queued." : "Position saved locally.");
  }

  function addNode() {
    const label = newNodeLabel.trim();
    if (!label) {
      return;
    }
    const current = workspaceRef.current;
    const index = current.nodes.length;
    commitWorkspace({
      ...current,
      nodes: [
        ...current.nodes,
        {
          id: createId("node"),
          label,
          kind: "service",
          x: 56 + (index % 3) * 230,
          y: 72 + Math.floor(index / 3) * 150,
        },
      ],
    });
    setNewNodeLabel("");
  }

  function updateNode(id: string, patch: Partial<Pick<DesignNode, "label" | "kind">>) {
    const current = workspaceRef.current;
    commitWorkspace({
      ...current,
      nodes: current.nodes.map((node) => (node.id === id ? { ...node, ...patch } : node)),
    });
  }

  function deleteNode(id: string) {
    const current = workspaceRef.current;
    commitWorkspace({
      ...current,
      nodes: current.nodes.filter((node) => node.id !== id),
      edges: current.edges.filter((edge) => edge.source !== id && edge.target !== id),
    });
  }

  function addEdge(event: FormEvent) {
    event.preventDefault();
    if (!edgeSource || !edgeTarget || edgeSource === edgeTarget) {
      return;
    }
    const current = workspaceRef.current;
    commitWorkspace({
      ...current,
      edges: [
        ...current.edges,
        {
          id: createId("edge"),
          source: edgeSource,
          target: edgeTarget,
          label: edgeLabel.trim(),
        },
      ],
    });
    setEdgeLabel("");
  }

  function deleteEdge(id: string) {
    const current = workspaceRef.current;
    commitWorkspace({
      ...current,
      edges: current.edges.filter((edge) => edge.id !== id),
    });
  }

  async function ensureSession() {
    if (session) {
      return session;
    }
    const created = await createWhiteboardTutorSession({
      candidateLevel: level,
      title: workspaceRef.current.title || "System design lab",
    });
    setSession(created);
    return created;
  }

  async function persistSnapshot(active: TutorSession, prefix: string) {
    const currentSnapshot = toSnapshot(workspaceRef.current);
    await appendTutorEvent(active.id, {
      eventType: "whiteboard.snapshot",
      idempotencyKey: createId(prefix),
      payload: currentSnapshot,
    });
    lastRemoteSnapshot.current = JSON.stringify(currentSnapshot);
  }

  async function saveRemote() {
    setBusy(true);
    setError(null);
    try {
      const active = await ensureSession();
      await persistSnapshot(active, "whiteboard-save");
      setStatus("Board saved to your account-backed design session.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save design session");
    } finally {
      setBusy(false);
    }
  }

  async function sendPrompt(prompt: string) {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const active = await ensureSession();
      await persistSnapshot(active, "whiteboard-before-coach");
      const reply = await sendTutorMessage(active.id, cleanPrompt, createId("design-tutor"));
      setTutorReply(reply.reply);
      setTutorPrompt("");
      setStatus(`Tutor responded with ${reply.intervention.kind.replaceAll("_", " ")} coaching.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Tutor request failed");
    } finally {
      setBusy(false);
    }
  }

  function askTutor(event: FormEvent) {
    event.preventDefault();
    void sendPrompt(tutorPrompt);
  }

  function exportWorkspace() {
    const current = workspaceRef.current;
    const blob = new Blob(
      [JSON.stringify({ exported_at: new Date().toISOString(), ...current }, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${current.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "skillforge-design"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const nodesById = useMemo(
    () => new Map(workspace.nodes.map((node) => [node.id, node])),
    [workspace.nodes],
  );

  return (
    <div className="page-content page-content--wide">
      <PageHeader
        eyebrow="DESIGN LAB"
        title="Design the system. Defend the trade-offs."
        description="Drag real architecture components, model explicit data flows, and let the tutor probe the exact structured design you are building."
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
        <strong>{status}</strong>
        <span>
          {session
            ? `Candidate-owned whiteboard session ${session.id.slice(0, 8)} is active.`
            : "Drag positions and notes recover locally; authenticated sessions add account persistence."}
        </span>
      </EvidenceNote>
      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.layout}>
        <aside className={`${styles.sidebar} panel`}>
          <SectionHeading eyebrow="STARTING FRAME" title="Architecture template" />
          <div className={styles.templates}>
            {designTemplates.map((template) => (
              <button
                className={template.id === workspace.templateId ? styles.templateActive : styles.template}
                key={template.id}
                onClick={() => chooseTemplate(template.id)}
                type="button"
              >
                <strong>{template.title}</strong>
                <span>{template.description}</span>
              </button>
            ))}
          </div>

          <label className={styles.field}>
            <span>Interview level</span>
            <select
              value={level}
              onChange={(event) => setLevel(event.target.value as CandidateLevel)}
            >
              {levels.map((candidateLevel) => (
                <option key={candidateLevel} value={candidateLevel}>
                  {candidateLevel.charAt(0).toUpperCase() + candidateLevel.slice(1)}
                </option>
              ))}
            </select>
          </label>

          <div className={styles.instructions}>
            <GripVertical size={16} />
            <div>
              <strong>Direct manipulation is live</strong>
              <span>Drag from the grip. Coordinates persist in the tutor snapshot.</span>
            </div>
          </div>
        </aside>

        <div className={styles.main}>
          <div className={styles.toolbar}>
            <label className={styles.titleField}>
              <span>Document title</span>
              <input
                value={workspace.title}
                onChange={(event) =>
                  commitWorkspace({ ...workspaceRef.current, title: event.target.value })
                }
              />
            </label>
            <span>{session ? "Autosave: account + local" : "Autosave: local"}</span>
          </div>

          <div
            aria-label="Architecture canvas"
            className={styles.stage}
            role="region"
            onPointerCancel={finishDrag}
            onPointerLeave={(event) => {
              if (event.buttons === 0) {
                finishDrag();
              }
            }}
            onPointerMove={moveDrag}
            onPointerUp={finishDrag}
            ref={stageRef}
          >
            <svg aria-hidden="true" className={styles.links}>
              <defs>
                <marker
                  id="design-arrow"
                  markerHeight="7"
                  markerWidth="8"
                  orient="auto"
                  refX="7"
                  refY="3.5"
                >
                  <polygon points="0 0, 8 3.5, 0 7" />
                </marker>
              </defs>
              {workspace.edges.map((edge) => {
                const source = nodesById.get(edge.source);
                const target = nodesById.get(edge.target);
                if (!source || !target) {
                  return null;
                }
                return (
                  <line
                    key={edge.id}
                    markerEnd="url(#design-arrow)"
                    x1={source.x + NODE_WIDTH / 2}
                    x2={target.x + NODE_WIDTH / 2}
                    y1={source.y + NODE_HEIGHT / 2}
                    y2={target.y + NODE_HEIGHT / 2}
                  />
                );
              })}
            </svg>

            {workspace.nodes.map((node) => (
              <article
                className={styles.node}
                data-node-id={node.id}
                key={node.id}
                style={{ left: node.x, top: node.y }}
              >
                <div className={styles.nodeTop}>
                  <button
                    aria-label={`Move ${node.label}`}
                    className={styles.dragHandle}
                    onPointerDown={(event) => beginDrag(event, node)}
                    type="button"
                  >
                    <GripVertical size={15} />
                  </button>
                  <select
                    aria-label={`Type ${node.label}`}
                    value={node.kind}
                    onChange={(event) => updateNode(node.id, { kind: event.target.value })}
                  >
                    {nodeKinds.map((kind) => (
                      <option key={kind} value={kind}>
                        {kind}
                      </option>
                    ))}
                  </select>
                  <button
                    aria-label={`Remove ${node.label}`}
                    className={styles.remove}
                    onClick={() => deleteNode(node.id)}
                    type="button"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <input
                  aria-label={`Name ${node.label}`}
                  className={styles.nodeLabel}
                  value={node.label}
                  onChange={(event) => updateNode(node.id, { label: event.target.value })}
                />
              </article>
            ))}
          </div>

          <div className={styles.canvasControls}>
            <div className={styles.addNode}>
              <input
                aria-label="New component name"
                placeholder="Add service, queue, store, model..."
                value={newNodeLabel}
                onChange={(event) => setNewNodeLabel(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    addNode();
                  }
                }}
              />
              <button className="button button--primary" onClick={addNode} type="button">
                <Plus size={15} /> Add component
              </button>
            </div>

            <form className={styles.edgeForm} onSubmit={addEdge}>
              <select
                aria-label="Connection source"
                value={edgeSource}
                onChange={(event) => setEdgeSource(event.target.value)}
              >
                <option value="">Source</option>
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
                <option value="">Target</option>
                {workspace.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label}
                  </option>
                ))}
              </select>
              <input
                aria-label="Connection label"
                placeholder="HTTP, events, reads..."
                value={edgeLabel}
                onChange={(event) => setEdgeLabel(event.target.value)}
              />
              <button className="button button--secondary" type="submit">
                <ArrowRight size={14} /> Connect
              </button>
            </form>
          </div>

          {workspace.edges.length ? (
            <div aria-label="Connection list" className={styles.edgeList}>
              {workspace.edges.map((edge) => (
                <div key={edge.id}>
                  <span>
                    {nodesById.get(edge.source)?.label ?? edge.source}
                    <ArrowRight size={12} />
                    {nodesById.get(edge.target)?.label ?? edge.target}
                    {edge.label ? <em>{edge.label}</em> : null}
                  </span>
                  <button aria-label={`Remove connection ${edge.id}`} onClick={() => deleteEdge(edge.id)}>
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <div className={styles.notes}>
            <label>
              <span>Requirements and success metrics</span>
              <textarea
                placeholder="One requirement per line: throughput, latency, availability, privacy..."
                value={workspace.requirements}
                onChange={(event) =>
                  commitWorkspace({ ...workspaceRef.current, requirements: event.target.value })
                }
              />
            </label>
            <label>
              <span>Assumptions, risks, and trade-offs</span>
              <textarea
                placeholder="One note per line: failure modes, ownership, rejected alternatives..."
                value={workspace.notes}
                onChange={(event) =>
                  commitWorkspace({ ...workspaceRef.current, notes: event.target.value })
                }
              />
            </label>
          </div>

          <section className={`${styles.tutor} panel`}>
            <div className={styles.tutorHeader}>
              <Bot size={20} />
              <div>
                <strong>Architecture interviewer</strong>
                <span>Every probe is grounded in the latest structured snapshot.</span>
              </div>
            </div>

            <div className={styles.quickPrompts}>
              {quickPrompts.map((item) => (
                <button
                  disabled={busy}
                  key={item.label}
                  onClick={() => void sendPrompt(item.prompt)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tutorReply ? <p className={styles.reply}>{tutorReply}</p> : null}

            <form className={styles.tutorForm} onSubmit={askTutor}>
              <input
                aria-label="Ask architecture tutor"
                placeholder={`Challenge my ${activeTemplate.title.toLowerCase()}...`}
                value={tutorPrompt}
                onChange={(event) => setTutorPrompt(event.target.value)}
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
