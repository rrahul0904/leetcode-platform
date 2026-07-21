"use client";

import { Box, Download, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { EvidenceNote, PageHeader, SectionHeading } from "@/components/page-ui";
import { designTemplates } from "@/lib/product-data";

type DesignNode = { id: number; label: string; type: string };
type Workspace = { templateId: string; title: string; requirements: string; assumptions: string; nodes: DesignNode[] };
const storageKey = "rigor-design-lab-draft-v1";

function initialWorkspace(templateId: string = designTemplates[0].id): Workspace {
  const template = designTemplates.find((item) => item.id === templateId) ?? designTemplates[0];
  return { templateId: template.id, title: `Untitled ${template.title}`, requirements: "", assumptions: "", nodes: template.nodes.map((label, index) => ({ id: index + 1, label, type: index === 0 ? "edge" : "service" })) };
}

export function DesignLab() {
  const [workspace, setWorkspace] = useState<Workspace>(() => initialWorkspace());
  const [saved, setSaved] = useState(false);
  const [newNode, setNewNode] = useState("");
  const activeTemplate = designTemplates.find((item) => item.id === workspace.templateId) ?? designTemplates[0];

  useEffect(() => {
    let frame = 0;
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored) {
        const recovered = JSON.parse(stored) as Workspace;
        frame = window.requestAnimationFrame(() => setWorkspace(recovered));
      }
    } catch { window.localStorage.removeItem(storageKey); }
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function update(next: Workspace) {
    setWorkspace(next);
    window.localStorage.setItem(storageKey, JSON.stringify(next));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1000);
  }
  function chooseTemplate(templateId: string) { update(initialWorkspace(templateId)); }
  function addNode() {
    const label = newNode.trim();
    if (!label) return;
    update({ ...workspace, nodes: [...workspace.nodes, { id: Date.now(), label, type: "service" }] });
    setNewNode("");
  }
  function exportWorkspace() {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), ...workspace }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${workspace.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "rigor-design"}.json`; anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page-content page-content--wide">
      <PageHeader eyebrow="DESIGN LAB" title="Make architecture reasoning inspectable." description="Start from a structured template, capture requirements and assumptions, arrange system boundaries, and export the draft. Work is autosaved in this browser only." actions={<button className="button button--dark" onClick={exportWorkspace}><Download size={15} /> Export JSON</button>} />
      <EvidenceNote tone="success"><strong>{saved ? "Draft saved locally." : "Browser draft recovery is enabled."}</strong><span>No design content leaves this device or reaches an AI provider.</span></EvidenceNote>
      <section className="design-layout section-block">
        <aside className="template-rail panel"><SectionHeading eyebrow="TEMPLATES" title="Starting frame" />{designTemplates.map((template) => <button className={template.id === workspace.templateId ? "template-option template-option--active" : "template-option"} key={template.id} onClick={() => chooseTemplate(template.id)}><Box size={17} /><span><strong>{template.title}</strong><small>{template.description}</small></span></button>)}<button className="button button--ghost button--full" onClick={() => chooseTemplate(workspace.templateId)}><RotateCcw size={15} /> Reset template</button></aside>
        <div className="design-workspace">
          <div className="design-toolbar"><label><span>Document title</span><input value={workspace.title} onChange={(event) => update({ ...workspace, title: event.target.value })} /></label><span className="save-indicator"><Save size={14} /> Autosave: local</span></div>
          <div className="architecture-canvas" aria-label={`${activeTemplate.title} component canvas`}>
            <div className="canvas-label"><span>{activeTemplate.title}</span><small>Logical sequence · drag positioning is scheduled for the React Flow execution milestone</small></div>
            <div className="node-flow">{workspace.nodes.map((node, index) => <div className="design-node" key={node.id}><span>{node.type}</span><strong contentEditable suppressContentEditableWarning onBlur={(event) => update({ ...workspace, nodes: workspace.nodes.map((item) => item.id === node.id ? { ...item, label: event.currentTarget.textContent || item.label } : item) })}>{node.label}</strong><button aria-label={`Remove ${node.label}`} onClick={() => update({ ...workspace, nodes: workspace.nodes.filter((item) => item.id !== node.id) })}><Trash2 size={13} /></button>{index < workspace.nodes.length - 1 && <i aria-hidden="true">→</i>}</div>)}</div>
            <div className="add-node"><input value={newNode} onChange={(event) => setNewNode(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addNode(); }} placeholder="Add a service, store, queue, or control" /><button className="button button--primary" onClick={addNode}><Plus size={15} /> Add component</button></div>
          </div>
          <div className="design-notes"><label><span>Requirements and success metrics</span><textarea value={workspace.requirements} onChange={(event) => update({ ...workspace, requirements: event.target.value })} placeholder="Functional needs, scale, latency, availability, consistency, privacy…" /></label><label><span>Assumptions, risks, and open questions</span><textarea value={workspace.assumptions} onChange={(event) => update({ ...workspace, assumptions: event.target.value })} placeholder="Traffic shape, failure modes, ownership, migration constraints…" /></label></div>
        </div>
      </section>
    </div>
  );
}
