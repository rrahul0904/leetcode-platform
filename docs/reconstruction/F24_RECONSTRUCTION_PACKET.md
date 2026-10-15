# F24 Reconstruction Packet

Packet status: **READY for bounded architecture/runtime hardening; NOT READY for production certification.**

## Inputs and evidence validation

Validated repository/PR/deployment evidence: REA-001 through REA-009. Donor-specific behavior is UNKNOWN (REA-010); protected Preview application behavior is UNKNOWN (REA-003, 011). No donor implementation or content is used as source material.

## Safety boundary

Candidate code runs only in the configured isolated provider. No execution is accepted by hosted `KUBERNETES_JOB` until its worker, authoritative state, and network route are certified. Hidden tests and canonical answers remain server-side. The application database is authoritative for candidate and execution state. A second isolated controller database cannot be treated as equivalent evidence.

## Clean-room work packet: hosted execution fail-closed

- Evidence: REA-004, REA-006, REA-007.
- Decision: REJECT Kubernetes for enabled V1 execution; retain source as deferred infrastructure.
- Mapping: IMPROVE safety and reliability.
- Required behavior: hosted K8s Run/Submit returns 503 before enqueue; readiness is `not_ready`; Terraform cannot enable disconnected EKS resources.
- Acceptance tests: K8s request adapter fails closed; readiness identifies the uncertified authoritative state path; Vercel Sandbox credential validation continues to work; Terraform validates while disabled and rejects enabled configuration.
- Verification: see `test_execution_plane.py`, `test_platform_core.py`, Terraform SaaS CI and exact-head GitHub checks after implementation.

## Remaining unknowns before user-facing production work

1. Authorized Preview access to prove `/livez`, `/readyz`, Clerk, database ownership/RLS and durable persistence.
2. Vercel Sandbox credentials and exact deployed runtime behavior, including Python and SQL Run/Submit.
3. Current production migration version and content inventory.
4. Donor public behavior and licensed evidence, if donor-equivalence remains a requirement.

These unknowns block claims of shipped or certified behavior. They do not block local architecture hardening and tests.
