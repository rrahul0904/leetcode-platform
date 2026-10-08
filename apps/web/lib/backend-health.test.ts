import { describe, expect, it } from "vitest";

import { isPublicBackendHealthPath } from "./backend-health";

describe("isPublicBackendHealthPath", () => {
  it.each([
    { label: "livez", path: ["livez"] },
    { label: "readyz", path: ["readyz"] },
  ])("allows the public health endpoint $label", ({ path }) => {
    expect(isPublicBackendHealthPath(path)).toBe(true);
  });

  it.each([
    { label: "auth", path: ["api", "v1", "auth", "me"] },
    { label: "tutor", path: ["api", "v1", "tutor", "capabilities"] },
    { label: "nested health", path: ["livez", "details"] },
    { label: "empty", path: [] },
  ])("keeps the $label path protected", ({ path }) => {
    expect(isPublicBackendHealthPath(path)).toBe(false);
  });
});
