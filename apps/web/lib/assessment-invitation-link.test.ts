import { describe, expect, it } from "vitest";

import {
  buildCandidateInvitationLink,
  readCandidateInvitationFragment,
} from "./assessment-invitation-link";

const credentials = {
  invitationId: "81c41108-2879-412f-a011-0ac620fa4575",
  acceptanceSecret: "tCjQ6gvdvpuPVdxDVhpy7K68xHGYZ02U0dl5WbUId_ZDkn6p9-2tqSTvvjXrP-Au",
};

describe("single-use employer assessment invitation links", () => {
  it("carries the token in the fragment only, with no URL query or logged server path", () => {
    const link = buildCandidateInvitationLink("https://interview.skillforge.example", credentials);
    const url = new URL(link);
    expect(url.origin).toBe("https://interview.skillforge.example");
    expect(url.pathname).toBe("/assessments");
    expect(url.search).toBe("");
    expect(url.href.split("#")[0]).not.toContain(credentials.acceptanceSecret);
    expect(readCandidateInvitationFragment(url.hash)).toEqual(credentials);
  });

  it("works on local development origins without disabling HTTPS production protection", () => {
    expect(buildCandidateInvitationLink("http://localhost:3001", credentials)).toContain("#invitation=");
    expect(() => buildCandidateInvitationLink("http://app.skillforge.example", credentials)).toThrow(
      "HTTPS",
    );
  });

  it("rejects missing, malformed, duplicate, or unrelated tokens", () => {
    const valid = buildCandidateInvitationLink("https://example.com", credentials);
    const hash = new URL(valid).hash;
    expect(readCandidateInvitationFragment("")).toBeNull();
    expect(readCandidateInvitationFragment("#other=message")).toBeNull();
    expect(readCandidateInvitationFragment("#invitation=bad&access=short")).toBeNull();
    expect(readCandidateInvitationFragment(hash + "&access=duplicate")).toBeNull();
    expect(readCandidateInvitationFragment(hash + "&tracking=true")).toBeNull();
    expect(readCandidateInvitationFragment(hash.replace(credentials.acceptanceSecret, "bad!"))).toBeNull();
    expect(() =>
      buildCandidateInvitationLink("https://example.com", {
        ...credentials, invitationId: "invalid",
      }),
    ).toThrow("Invalid invitation");
  });
});
