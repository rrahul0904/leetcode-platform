# Capability Matrix

Current repository scope and implementation disposition. “Implemented” means code exists; it does not mean the capability is production-certified. Evidence IDs refer to [REA_EVIDENCE_LEDGER.md](REA_EVIDENCE_LEDGER.md).

| Capability | Current evidence/status | F24 decision | Match / Improve / New / Omit | Acceptance gate |
|---|---|---|---|---|
| Question bank and governed publication | API/content schemas, review surfaces, and quality-gate docs exist; live published count UNKNOWN (REA-009). | REUSE, then ADAPT | IMPROVE | Current DB inventory, rights/provenance, review approvals, executable fixtures, public-payload leakage tests. |
| Python / SQL Run and Submit | Durable execution request/result schema and API routes exist; hosted user journey UNKNOWN (REA-003, 004). | REUSE | IMPROVE | Exact Preview journey through isolated provider, public/hidden tests, persistence, retries and adversarial limits. |
| Candidate progress/readiness | Persistence models and API/UI surfaces exist; production account persistence UNKNOWN. | REUSE | IMPROVE | Authenticated cross-session state and deterministic evidence source tests. |
| Clerk identity and authorization | Clerk/OIDC configuration and server-side principal flows exist; live browser auth UNKNOWN. | REUSE | IMPROVE | Sign-up/sign-in/logout, durable identity mapping, denial cases, direct PostgreSQL RLS checks. |
| Vercel Sandbox execution | Canonical V1 provider is configured in Vercel app config; project credentials/runtime health UNKNOWN. | ADAPT | IMPROVE | Exact Preview Run/Submit and isolation certification; credentials available only to trusted API dispatch. |
| Kubernetes/EKS execution | Terraform and controller source exist, but API/controller state and network authority conflict (REA-004, 006). | REJECT for V1 | OMIT from enabled production | Requests return 503; readiness not ready; Terraform enable flag rejected until shared authoritative state/network proof. |
| AI tutor | Tutor sessions/events, provider and context-boundary docs exist; deployed workflow UNKNOWN. | REUSE | IMPROVE | Persistent session, safe-context tests, no hidden evaluation leakage, no mastery from chat alone. |
| Mock interviews / Think Aloud | Session/report models and route surfaces exist; hosted persistence and interview behavior UNKNOWN. | REUSE | IMPROVE | Deterministic persistent assessment evidence; candidate turn control; assessment-mode no-coaching checks. |
| PR Review Lab | Session/comment models and product docs exist; client/server gold-data boundary requires review. | ADAPT | IMPROVE | Gold findings remain server-side; deterministic grading and persisted judgment evidence. |
| Company readiness | Company/knowledge models and surfaces exist; source freshness and observation provenance UNKNOWN. | ADAPT | IMPROVE | Source-backed facts with timestamps and uncertainty; never assert unverified interview sightings. |
| AI Arena | Generation/rating/result models exist; hosted isolation and atomic quotas UNKNOWN. | REUSE | IMPROVE | Immutable generated source, hidden tests private, authoritative score/rating, isolation and concurrency tests. |
| Learning paths / Study Workspace | Learning plan models/routes exist; any browser-local state and account synchronization require route-level audit. | ADAPT | IMPROVE | Candidate-owned persistence survives refresh/login and contributes only verified learning evidence. |
| Code Typing / Typing Arcade | First-party code-typing and falling-word engine sources exist; production accessibility/device behavior UNKNOWN. | REUSE | IMPROVE | Original examples, deterministic scoring, keyboard/screen-reader/mobile tests; arcade metrics excluded from mastery. |
| Billing / entitlements | Subscription and entitlement models exist; live provider/webhook journey UNKNOWN. | ADAPT | NEW | Signature/idempotency, server-enforced entitlements, cancellation/grace behavior and hosted checkout tests. |
| Donor-specific proprietary behavior/content | No donor evidence or license provided (REA-010). | REJECT unsupported claims | OMIT | Reconsider only with public/authorized evidence and clean-room packet. |

## Current architecture boundary

Canonical V1 is Vercel Next.js → same-origin FastAPI BFF/service → Clerk-verified identity → Neon/PostgreSQL authoritative state → Vercel Sandbox for hostile candidate code. AWS/EKS source is deferred and fail-closed until it uses the same authoritative execution state and a certified network path. Runtime health, real authentication, production content counts, RLS against production, and all hosted workflows remain UNKNOWN while protected Preview probes are blocked (REA-003, 011).
