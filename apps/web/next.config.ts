import type { NextConfig } from "next";

const authMode =
  process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ??
  (process.env.VERCEL ? "clerk" : "local");
const configuredApiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL?.trim();
const apiUrl =
  configuredApiUrl ||
  (authMode === "clerk" || process.env.VERCEL
    ? "/api/backend"
    : "http://localhost:8002");

if (process.env.VERCEL && apiUrl !== "/api/backend") {
  throw new Error(
    "SkillForge Vercel deployments must use the same-origin /api/backend boundary.",
  );
}

function apiConnectSources(value: string) {
  if (value.startsWith("/")) return [];
  try {
    const origin = new URL(value).origin;
    return [origin, origin.replace(/^http/, "ws")];
  } catch {
    throw new Error(
      "NEXT_PUBLIC_RIGOR_API_URL must be a same-origin path or an absolute HTTP(S) URL.",
    );
  }
}

const connectSources = [
  "'self'",
  ...apiConnectSources(apiUrl),
  "https://*.clerk.accounts.dev",
  "https://clerk-telemetry.com",
  "https://*.clerk-telemetry.com",
  "https://*.protect.clerk.com:*",
];

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data: blob: https://img.clerk.com",
  "font-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.clerk.accounts.dev https://challenges.cloudflare.com https://*.protect.clerk.com",
  `connect-src ${connectSources.join(" ")}`,
  "frame-src 'self' https://challenges.cloudflare.com https://*.protect.clerk.com",
  "worker-src 'self' blob:",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
