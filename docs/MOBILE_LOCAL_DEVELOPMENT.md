# Mobile local development

## Requirements

Use the repository-pinned Node/pnpm versions and the Expo SDK declared by `apps/mobile/package.json`.

From the repository root:

```bash
corepack enable
corepack prepare pnpm@11.10.0 --activate
pnpm install --frozen-lockfile
pnpm dev:mobile
```

Or:

```bash
pnpm --filter @rigor/mobile start
pnpm --filter @rigor/mobile ios
pnpm --filter @rigor/mobile android
```

## API URL

The mobile app reads `EXPO_PUBLIC_API_URL`.

Typical development values:

- iOS simulator: `http://127.0.0.1:8002`
- Android emulator: `http://10.0.2.2:8002`
- physical device: `http://<developer-LAN-IP>:8002`

Do not commit a developer LAN address.

## Local OIDC

The local provider accepts `rigor://auth/callback` while local OIDC is enabled. Production must use the real provider's registered native redirect/app/universal-link configuration and must not enable the repository local provider.

## Public Expo configuration

The checked-in `.env.example` contains only public client configuration. OIDC provider secrets, database credentials, AWS credentials, AI provider keys, and backend signing secrets must never use `EXPO_PUBLIC_*`.
