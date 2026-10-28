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
