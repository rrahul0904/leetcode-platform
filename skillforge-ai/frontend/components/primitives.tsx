import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function GradientCard({ children, className = "", glow = "cyan" }: { children: ReactNode; className?: string; glow?: "cyan" | "violet" | "emerald" | "none" }) {
  return <div className={cn("sf-card", glow !== "none" && `sf-glow-${glow}`, className)}>{children}</div>;
}

export function PrimaryButton({ children, className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={cn("sf-btn sf-btn-primary", className)} {...props}>{children}</button>;
}

export function SecondaryButton({ children, className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={cn("sf-btn sf-btn-secondary", className)} {...props}>{children}</button>;
}

export function DifficultyBadge({ value }: { value: string }) {
  return <span className={cn("sf-badge", `sf-difficulty-${value.toLowerCase()}`)}>{value}</span>;
}

export function TopicBadge({ children }: { children: ReactNode }) {
  return <span className="sf-badge sf-topic-badge">{children}</span>;
}

export function StatusBadge({ status }: { status: "ready" | "warning" | "error" | "ai" }) {
  const labels = { ready: "Ready", warning: "Needs attention", error: "Failed", ai: "AI ready" };
  return <span className={cn("sf-status-badge", `sf-status-${status}`)}><span className="sf-status-dot" />{labels[status]}</span>;
}

export function MetricCard({ label, value, helper, accent = "cyan" }: { label: string; value: string; helper: string; accent?: "cyan" | "violet" | "emerald" | "amber" }) {
  return <GradientCard glow={accent === "violet" ? "violet" : accent === "emerald" ? "emerald" : "cyan"} className="sf-metric-card"><div className="sf-metric-label">{label}</div><div className="sf-metric-value">{value}</div><div className="sf-metric-helper">{helper}</div></GradientCard>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="sf-page-header"><div><div className="sf-eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="sf-page-actions">{actions}</div>}</div>;
}

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return <div className="sf-skeleton-stack" aria-label="Loading">{Array.from({ length: lines }).map((_, i) => <div key={i} className="sf-skeleton" style={{ width: `${92 - i * 11}%` }} />)}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="sf-empty"><div className="sf-empty-icon">◎</div><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function ErrorState({ title, description, technical, onRetry }: { title: string; description: string; technical?: string; onRetry?: () => void }) {
  return <div className="sf-error-state"><AlertTriangle size={20} /><div><strong>{title}</strong><p>{description}</p>{technical && <details><summary>Technical details</summary><pre>{technical}</pre></details>}{onRetry && <SecondaryButton onClick={onRetry}>Retry</SecondaryButton>}</div></div>;
}

export function SuccessState({ title, description }: { title: string; description: string }) {
  return <div className="sf-success-state"><CheckCircle2 size={20} /><div><strong>{title}</strong><p>{description}</p></div></div>;
}

export function BusyLabel({ children }: { children: ReactNode }) {
  return <span className="sf-busy"><Loader2 size={14} className="sf-spin" />{children}</span>;
}
