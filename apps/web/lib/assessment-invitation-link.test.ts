import { describe, expect, it } from "vitest";

import {
  buildCandidateInvitationLink,
  readCandidateInvitationFragment,
  safeSignInReturnPath,
  stashPendingCandidateInvitation,
  takePendingCandidateInvitation,
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

describe("candidate invitation sign-in handoff", () => {
  function tabStorage() {
    const data = new Map<string, string>();
    return {
      data,
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => { data.set(key, value); },
      removeItem: (key: string) => { data.delete(key); },
    };
  }

  it("is tab scoped, consumed once, and never retained after login", () => {
    const storage = tabStorage();
    stashPendingCandidateInvitation(storage, credentials, 1000);
    expect(storage.data.size).toBe(1);
    expect(takePendingCandidateInvitation(storage, 5000)).toEqual(credentials);
    expect(storage.data.size).toBe(0);
    expect(takePendingCandidateInvitation(storage, 5000)).toBeNull();
  });

  it("expires pending credentials, rejects corruption and removes expired storage", () => {
    const storage = tabStorage();
    stashPendingCandidateInvitation(storage, credentials, 1000);
    expect(takePendingCandidateInvitation(storage, 1000 + 21 * 60 * 1000)).toBeNull();
    expect(storage.data.size).toBe(0);
    stashPendingCandidateInvitation(storage, credentials, 1000);
    expect(takePendingCandidateInvitation(storage, 900)).toBeNull();
  });

  it("never redirects candidate login to an external origin or token-bearing URL", () => {
    expect(safeSignInReturnPath("/assessments")).toBe("/assessments");
    for (const input of [
      "https://evil.example", "//evil.example", "/\\evil.example",
      "/assessments?access=SECRET", "/assessments#invitation=SECRET",
      "/%2F%2Fevil.example",
    ]) {
      expect(safeSignInReturnPath(input)).toBe("/workspace");
    }
  });
});
