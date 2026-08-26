import { auth } from "@clerk/nextjs/server";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function backendOrigin(): string {
  const value = process.env.RIGOR_BACKEND_ORIGIN?.trim().replace(/\/+$/, "");
  if (!value || !value.startsWith("https://")) {
    throw new Error("RIGOR_BACKEND_ORIGIN must be an HTTPS origin in Clerk mode.");
  }
  return value;
}

async function proxyRequest(request: Request, context: RouteContext): Promise<Response> {
  const { isAuthenticated, getToken } = await auth();
  if (!isAuthenticated) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }

  const template = process.env.CLERK_JWT_TEMPLATE?.trim() || "skillforge-api";
  const token = await getToken({ template });
  if (!token) {
    return Response.json({ detail: "Unable to mint API token" }, { status: 401 });
  }

  const { path } = await context.params;
  const target = new URL(
    `${backendOrigin()}/${path.map((segment) => encodeURIComponent(segment)).join("/")}`,
  );
  target.search = new URL(request.url).search;

  const headers = new Headers(request.headers);
  headers.delete("cookie");
  headers.delete("host");
  headers.delete("content-length");
  headers.set("authorization", `Bearer ${token}`);
  headers.set("x-skillforge-client", "vercel-bff");

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    ...(body ? { body } : {}),
    redirect: "manual",
    cache: "no-store",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("set-cookie");
  responseHeaders.delete("content-length");
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export function GET(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export function POST(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export function PUT(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export function PATCH(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}

export function DELETE(request: Request, context: RouteContext) {
  return proxyRequest(request, context);
}
