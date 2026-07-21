# Security Test Plan

CI and isolated environments cover dependency and secret scanning, static analysis, IaC policy, container scanning/SBOM/signing, permission-negative tests, JWT/OIDC attacks, IDOR and tenant isolation, input/output limits, CSP/XSS/CSRF/SSRF, webhook signature/idempotency, upload polyglots, prompt injection/exfiltration, and candidate-safe content projections.

Sandbox testing runs only in a dedicated environment and includes network, filesystem, namespace, capabilities, credentials, metadata, resources, timeout, fork bomb, output flood, cleanup, cross-user, SQL catalog, lock, and destructive-query cases. Passing configuration review alone is not completion evidence.

