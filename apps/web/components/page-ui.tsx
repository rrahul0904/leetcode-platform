import { AlertTriangle, ArrowRight, CheckCircle2, LoaderCircle, Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}

export function SectionHeading({ eyebrow, title, aside }: { eyebrow?: string; title: string; aside?: ReactNode }) {
  return <div className="section-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>{aside}</div>;
}

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return <div className="state-panel" aria-live="polite"><LoaderCircle className="spin" size={24} /><strong>{label}</strong></div>;
}

export function ErrorState({ retry }: { retry?: () => void }) {
  return <div className="state-panel state-panel--error" role="alert"><AlertTriangle size={24} /><strong>The local API did not respond.</strong><p>Check the API container and retry the request.</p>{retry && <button className="button button--dark" onClick={retry}>Retry</button>}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="state-panel"><Search size={24} /><strong>{title}</strong><p>{description}</p>{action}</div>;
}

export function EvidenceNote({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "success" | "warning" }) {
  return <div className={`evidence-note evidence-note--${tone}`}>{tone === "success" ? <CheckCircle2 size={19} /> : tone === "warning" ? <AlertTriangle size={19} /> : <FlaskConicalIcon />}<div>{children}</div></div>;
}

function FlaskConicalIcon() {
  return <span className="evidence-note__mark" aria-hidden="true">R</span>;
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link className="text-link" href={href}>{children}<ArrowRight size={14} /></Link>;
}
