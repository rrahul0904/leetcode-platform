# Rigor mobile authentication

## Protocol

The native application uses OIDC Authorization Code + PKCE through the system browser. The public mobile client ID and issuer may be included in app configuration; provider client secrets may not.

Redirect scheme during development:

```text
rigor://auth/callback
```

Production should additionally configure verified iOS universal links and Android app links where supported by the selected OIDC provider.

## Token storage

Access/refresh tokens are stored with Expo SecureStore. AsyncStorage and SQLite are not authentication-token stores.

The shared API transport receives a `getAccessToken()` callback so storage policy is platform-specific. On HTTP 401 the native client clears the local secure session and returns to authentication rather than trusting stale identity.

## Principal

After token exchange the app calls FastAPI `/api/v1/auth/me`. Native candidate navigation requires the normalized principal to contain the candidate role. Candidate ID, organization scope, and authorization decisions remain server-side.

## Local development

The repository local OIDC provider remains explicitly local. When enabled, settings ensure `rigor://auth/callback` is present even if Docker supplies a web-only redirect list through environment configuration.

Production must set `RIGOR_LOCAL_OIDC_ENABLED=false` and use an external production OIDC issuer/audience/JWKS configuration.
