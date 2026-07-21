# Secure Execution Plane

## Python

The API creates an execution request; the controller validates limits and submits a Kubernetes Job to an isolated EKS cluster/node group. The Job uses an immutable signed runtime image, gVisor RuntimeClass, deny-all network policy, read-only root, non-root UID, dropped capabilities, RuntimeDefault seccomp, PID/CPU/memory/file/output limits, an ephemeral workspace, deadline, and TTL cleanup.

The workload receives only an execution ID and sanitized challenge bundle. It receives no application, cloud, database, registry, Kubernetes, or host credentials. Results are bounded, normalized, audited, and returned through the controller—not through direct access to application services.

## SQL

SQL attempts receive a non-superuser role and disposable PostgreSQL challenge database created from a versioned template. The runner configures statement, lock, and idle-transaction timeouts; row/output limits; restricted extensions; no production routes; and no other attempt access. PostgreSQL executes validation and JSON plans. SQLGlot, if later approved, is static analysis only. Cleanup drops the disposable database or reverts the isolated snapshot.

## Completion tests

Network, filesystem, CPU, memory, PID, timeout, output, cross-user, credential, metadata, fork-bomb, malicious import, query-lock, catalog-access, and cleanup tests must pass in the production-equivalent boundary.

