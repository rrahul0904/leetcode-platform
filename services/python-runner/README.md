# Python runner

This directory contains the first production-oriented Python sandbox runtime for Rigor.

The runner is **not** a security boundary by itself. Production isolation still depends on the dedicated Kubernetes execution plane, gVisor, default-deny networking, resource quotas, a dedicated no-credential service account, and trusted dispatcher cleanup.

## Contract

The runner receives one mounted JSON request containing:

- `schema_version`;
- `execution_id`;
- candidate `source_code`;
- the required `entrypoint`;
- public/hidden **test inputs**.

Expected outputs are deliberately excluded from the sandbox request. Trusted dispatcher/evaluation code compares returned actual values with expected values after the Job completes.

The runner:

1. validates the bounded request;
2. runs each test in a child Python interpreter using `-I -S`;
3. applies OS process/file/fd/process-count limits in addition to Kubernetes cgroup limits;
4. supplies a minimal environment with no AWS credentials;
5. restricts candidate imports and direct file/input/eval helpers;
6. captures public stdout/stderr with hard bounds;
7. does not surface hidden-test stdout/stderr;
8. emits one normalized `RIGOR_EXECUTION_RESULT:` JSON record for the trusted dispatcher.

Candidate source is never executed in FastAPI, Next.js, a trusted worker, RDS, or a mobile client.

## Image

Build using the version-controlled Dockerfile and tag with an immutable release or git SHA. Runtime job construction rejects mutable tags such as `latest` and `production`.

Example local build tag:

```text
runner-python:3.13-v1
```

Production should prefer an ECR digest reference after build, scan, SBOM, and signing gates are in place.
