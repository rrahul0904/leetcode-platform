export const dynamic = "force-dynamic";

function backendOrigin(): string {
  const value = process.env.RIGOR_BACKEND_ORIGIN?.trim().replace(/\/+$/, "");
  if (!value) {
    throw new Error("RIGOR_BACKEND_ORIGIN is not configured.");
  }
  if (!value.startsWith("https://") && !value.startsWith("http://")) {
    throw new Error("RIGOR_BACKEND_ORIGIN must be an HTTP(S) origin.");
  }
  return value;
}

function webhookHeaders(request: Request) {
  const headers = new Headers();
  headers.set("content-type", request.headers.get("content-type") || "application/json");
  for (const name of ["svix-id", "svix-timestamp", "svix-signature"] as const) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("x-skillforge-client", "clerk-webhook-ingress");
  return headers;
}

export async function POST(request: Request) {
  const body = await request.arrayBuffer();
  const upstream = await fetch(
    new URL("/api/v1/webhooks/clerk", `${backendOrigin()}/`),
    {
      method: "POST",
      headers: webhookHeaders(request),
      body,
      cache: "no-store",
      redirect: "manual",
    },
  );

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  const correlationId = upstream.headers.get("x-correlation-id");
  if (correlationId) responseHeaders.set("x-correlation-id", correlationId);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
