# Threat Model

| Threat | Primary controls | Required evidence |
| --- | --- | --- |
| Sandbox escape | gVisor, non-root, dropped capabilities, seccomp, no host mounts, one Job/submission | isolated escape suite and runtime audit |
| Credential/metadata theft | no credentials, deny-all egress, metadata blocking, separate account/VPC | credential and network probes fail |
| Cross-tenant access | authorization at four layers, RLS, tenant object keys | negative permission and isolation tests |
| SQL cross-user access | disposable database/schema, restricted role/catalog, cleanup | concurrent isolation suite |
| Prompt injection/exfiltration | typed tools, allowlists, context provenance, output scanning, consent | adversarial gateway tests |
| Hidden answer leakage | candidate-safe projections, separate objects/relations, audit | API contract and permission tests |
| Account takeover | Cognito MFA, PKCE, short tokens, secure recovery | OIDC security tests |
| Question scraping | quotas, behavioral rate limits, watermark/audit strategy, no bulk hidden content | abuse/load tests |
| Malicious uploads | content sniffing, size/type allowlists, quarantine scanning | known-malware and polyglot tests |
| Admin abuse | least privilege, separation of duties, append-only audit | review/publish override tests |
| Interview privacy | explicit recording consent, retention, encrypted private objects | consent and deletion tests |

Residual risk is reviewed before each production milestone. Sandbox completion requires external security review and cannot be inferred from configuration alone.

