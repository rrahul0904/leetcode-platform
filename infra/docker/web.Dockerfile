# syntax=docker/dockerfile:1.8

ARG NODE_IMAGE=node:24.18.0-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d

FROM ${NODE_IMAGE} AS builder
ARG NEXT_PUBLIC_RIGOR_API_URL=http://localhost:8002
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_RIGOR_API_URL=${NEXT_PUBLIC_RIGOR_API_URL}
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.10.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.base.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/api-client packages/api-client
RUN pnpm --filter @rigor/web build

FROM ${NODE_IMAGE} AS runtime
LABEL org.opencontainers.image.title="Rigor Web" \
      org.opencontainers.image.description="Rigor Next.js web application" \
      org.opencontainers.image.version="0.1.0-local"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3001 \
    HOSTNAME=0.0.0.0
WORKDIR /app

COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static

USER node
EXPOSE 3001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3001/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]

CMD ["node", "apps/web/server.js"]
