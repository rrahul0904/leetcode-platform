# Runbook: execution-plane emergency shutdown

Use this runbook for suspected sandbox escape, credential exposure, uncontrolled resource use, or execution-plane instability.

1. Stop dispatch from the trusted worker/service and prevent new queue claims.
2. Leave incoming execution requests durable/queued; do not delete canonical submission rows.
3. Scale execution worker/node capacity to zero where safe.
4. Delete active candidate Jobs/Pods and reconcile their database states to `INFRASTRUCTURE_ERROR` or the target cancellation state according to the execution-state rules.
5. Preserve EKS audit/control-plane logs, execution IDs, Job metadata, image digests, and correlation IDs.
6. Do not copy hidden tests or full candidate source into broad incident channels.
7. If AWS credential exposure is suspected, revoke/rotate the affected trusted role/secret and rebuild the execution nodes before dispatch resumes.
8. Re-run sandbox network/metadata/privilege regression tests before re-enabling staging dispatch.
9. Production dispatch resumes only after the cause is fixed and the same regression passes in staging.

The control plane is designed to remain available for profile/catalog/history/readiness while hostile execution is disabled.
