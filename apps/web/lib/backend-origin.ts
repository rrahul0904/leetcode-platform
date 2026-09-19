export function resolveBackendOrigin(
  rawValue: string | undefined,
  vercelEnv: string | undefined,
): string {
  const value = rawValue?.trim().replace(/\/+$/, "");
  if (!value) {
    throw new Error("RIGOR_BACKEND_ORIGIN is not configured.");
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("RIGOR_BACKEND_ORIGIN must be an HTTP(S) origin.");
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("RIGOR_BACKEND_ORIGIN must be an HTTP(S) origin.");
  }

  if (vercelEnv === "production") {
    const hostname = parsed.hostname.toLowerCase().replace(/\.$/, "");
    const isLoopback =
      hostname === "localhost" ||
      hostname.endsWith(".localhost") ||
      hostname === "0.0.0.0" ||
      hostname === "::1" ||
      hostname === "[::1]" ||
      /^127(?:\.|$)/.test(hostname);

    if (isLoopback) {
      throw new Error(
        "RIGOR_BACKEND_ORIGIN must not target localhost or a loopback address in production.",
      );
    }

    const isVercelInternal = hostname.endsWith(".vercel.internal");
    if (parsed.protocol !== "https:" && !isVercelInternal) {
      throw new Error(
        "RIGOR_BACKEND_ORIGIN must use HTTPS in production unless Vercel supplies an internal service URL.",
      );
    }
  }

  return value;
}
