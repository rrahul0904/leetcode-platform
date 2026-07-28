# Mobile security review

## Implemented controls

- Native authentication uses Authorization Code + PKCE.
- Tokens are stored with Expo SecureStore, not AsyncStorage.
- Shared HTTP transport obtains tokens through an injected provider; the transport itself does not depend on browser storage.
- Mobile candidate navigation rejects non-candidate principals.
- Candidate identity, organization, and permissions remain server-derived.
- No database, AWS, OIDC client secret, or AI provider secret is part of mobile configuration.
- Published question APIs remain the source for mobile catalog/detail content; hidden tests/solutions are not embedded in the bundle.
- Submit uses a unique idempotency key and mutations are not automatically retried.
- Drafts stored in SQLite are candidate-authored source only; authentication tokens remain in SecureStore.
- Candidate source is not sent to telemetry by this implementation.

## Outstanding production controls

- Register final iOS bundle identifier and Android application ID deliberately.
- Configure and validate universal links / Android app links.
- Register production native OIDC redirect URIs.
- Select crash/telemetry SDKs and configure source-code/PII redaction.
- Establish EAS/App Store/Play signing identities and access policy.
- Add device-level integration tests for expired-token refresh and malicious deep-link inputs.

## Execution boundary

The mobile client is never a grading sandbox. Any future offline code runner must be treated as a local convenience only and must not become authoritative evidence/readiness execution.
