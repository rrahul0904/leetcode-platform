import { auth, currentUser } from "@clerk/nextjs/server";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

type ClerkEmailAddress = {
  id: string;
  emailAddress: string;
  verification?: { status?: string | null } | null;
};

function backendOrigin(): string {
  const value = process.env.RIGOR_BACKEND_ORIGIN?.trim().replace(/\/+$/, "");
  if (!value) {
    throw new Error("RIGOR_BACKEND_ORIGIN is not configured.");
  }
  if (!value.startsWith("https://") && !value.startsWith("http://")) {
    throw new Error("RIGOR_BACKEND_ORIGIN must be an HTTP(S) origin.");
  }
  if (
    process.env.VERCEL_ENV === "production" &&
    value.startsWith("http://") &&
    !value.includes(".vercel.internal")
  ) {
    throw new Error(
      "RIGOR_BACKEND_ORIGIN must use HTTPS in production unless Vercel supplies an internal service URL.",
    );
  }
  return value;
}

function forwardedHeaders(request: Request, token: string) {
  const headers = new Headers(request.headers);
  headers.delete("cookie");
  headers.delete("host");
  headers.delete("content-length");
  headers.set("authorization", `Bearer ${token}`);
  headers.set("x-skillforge-client", "vercel-bff");
  return headers;
}

async function fetchUpstream(
  target: URL,
  request: Request,
  token: string,
  body?: ArrayBuffer,
) {
  return fetch(target, {
    method: request.method,
    headers: forwardedHeaders(request, token),
    ...(body ? { body } : {}),
    redirect: "manual",
    cache: "no-store",
  });
}

function candidateDisplayName(user: Awaited<ReturnType<typeof currentUser>>) {
  if (!user) return null;
  const fullName = [user.firstName, user.lastName]
    .filter((part): part is string => Boolean(part?.trim()))
    .join(" ")
    .trim();
  return fullName || user.username || null;
}

function primaryVerifiedEmail(
  user: NonNullable<Awaited<ReturnType<typeof currentUser>>>,
) {
  const addresses = user.emailAddresses as ClerkEmailAddress[];
  const primary = addresses.find(
    (address) => address.id === user.primaryEmailAddressId,
  );
  const selected = primary ?? addresses[0];
  if (!selected?.emailAddress) return null;
  const verified = selected.verification?.status === "verified";
  return { email: selected.emailAddress, verified };
}

async function reconcileCandidate(token: string) {
  const user = await currentUser();
  if (!user) return false;
  const email = primaryVerifiedEmail(user);
  const displayName =
    candidateDisplayName(user) ?? email?.email ?? "SkillForge Candidate";
  if (!email?.verified) return false;

  const response = await fetch(
    new URL("/api/v1/identity/reconcile", `${backendOrigin()}/`),
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-SkillForge-Client": "vercel-bff-reconcile",
      },
      body: JSON.stringify({
        subject: user.id,
        email: email.email,
        email_verified: true,
        display_name: displayName,
      }),
      cache: "no-store",
    },
  );
  return response.ok;
}

function isIdentityBootstrapPath(path: string[]) {
  return path.join("/") === "api/v1/auth/me";
}

async function sessionToken() {
  const { isAuthenticated, getToken } = await auth();
  if (!isAuthenticated) return null;

  const template = process.env.CLERK_JWT_TEMPLATE?.trim();
  return template ? getToken({ template }) : getToken();
}

async function proxyRequest(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const token = await sessionToken();
  if (!token) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }

  const { path } = await context.params;
  const target = new URL(
    `${backendOrigin()}/${path.map((segment) => encodeURIComponent(segment)).join("/")}`,
  );
  target.search = new URL(request.url).search;

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  let upstream = await fetchUpstream(target, request, token, body);

  if (upstream.status === 401 && isIdentityBootstrapPath(path)) {
    const reconciled = await reconcileCandidate(token);
    if (reconciled) {
      upstream = await fetchUpstream(target, request, token, body);
    }
  }

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
