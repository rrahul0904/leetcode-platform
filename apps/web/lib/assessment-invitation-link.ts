/**
 * One-use candidate invitations are transported in URL fragments, never in
 * query parameters. Fragments are not sent to HTTP servers or Referer headers.
 * The candidate page removes the fragment immediately after reading it.
 *
 * Do not log, track, persist, or prefetch these credentials.
 */
export type CandidateInvitationLink = {
  invitationId: string;
  acceptanceSecret: string;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SECRET = /^[a-zA-Z0-9_-]{48,128}$/;

function validCredentials(input: CandidateInvitationLink): boolean {
  return UUID.test(input.invitationId) && SECRET.test(input.acceptanceSecret);
}

export function buildCandidateInvitationLink(
  origin: string,
  credentials: CandidateInvitationLink,
): string {
  if (!validCredentials(credentials)) throw new Error("Invalid invitation credentials");
  const url = new URL("/assessments", origin);
  if (url.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(url.hostname)) {
    throw new Error("Candidate invitations require an HTTPS destination");
  }
  // Explicitly omit all query parameters; the one-use token is never routed
  // to the API until the authenticated candidate presses Start.
  url.search = "";
  url.hash = new URLSearchParams({
    invitation: credentials.invitationId,
    access: credentials.acceptanceSecret,
  }).toString();
  return url.toString();
}

export function readCandidateInvitationFragment(
  fragment: string,
): CandidateInvitationLink | null {
  if (!fragment.startsWith("#invitation=") || fragment.length > 300) return null;
  const params = new URLSearchParams(fragment.slice(1));
  const invitationId = params.get("invitation") ?? "";
  const acceptanceSecret = params.get("access") ?? "";
  if (
    params.size !== 2 ||
    !validCredentials({ invitationId, acceptanceSecret })
  ) return null;
  return { invitationId, acceptanceSecret };
}

/** Browser-tab-only handoff when the candidate must sign in first. */
const PENDING_KEY = "rigor.assessment.invitation-pending";
const PENDING_TTL_MS = 20 * 60 * 1000;

export function stashPendingCandidateInvitation(
  storage: Pick<Storage, "setItem">,
  credentials: CandidateInvitationLink,
  now = Date.now(),
): void {
  if (!validCredentials(credentials)) throw new Error("Invalid invitation credentials");
  storage.setItem(PENDING_KEY, JSON.stringify({ ...credentials, createdAt: now }));
}

/**
 * Read once, always delete, and reject stale or malformed credentials. This
 * intentionally uses sessionStorage, never localStorage or a server cookie.
 */
export function takePendingCandidateInvitation(
  storage: Pick<Storage, "getItem" | "removeItem">,
  now = Date.now(),
): CandidateInvitationLink | null {
  const raw = storage.getItem(PENDING_KEY);
  storage.removeItem(PENDING_KEY);
  if (!raw || raw.length > 512) return null;
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    const invitationId = data.invitationId;
    const acceptanceSecret = data.acceptanceSecret;
    if (
      typeof invitationId !== "string"
      || typeof acceptanceSecret !== "string"
      || typeof data.createdAt !== "number"
      || !Number.isFinite(data.createdAt)
      || now < data.createdAt
      || now - data.createdAt > PENDING_TTL_MS
    ) return null;
    const credentials: CandidateInvitationLink = { invitationId, acceptanceSecret };
    return validCredentials(credentials) ? credentials : null;
  } catch {
    return null;
  }
}

/** Login redirects are only allowed to a simple same-origin application path. */
export function safeSignInReturnPath(value: string | undefined | null): string {
  if (
    value
    && value.startsWith("/")
    && !value.startsWith("//")
    && !value.includes("\\")
    && /^\/[a-zA-Z0-9/_-]*$/.test(value)
  ) return value;
  return "/workspace";
}
