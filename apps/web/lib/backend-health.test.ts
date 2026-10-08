import { describe, expect, it } from "vitest";

import { isPublicBackendHealthPath } from "./backend-health";

describe("isPublicBackendHealthPath", () => {
  it.each([["livez"], ["readyz"]])("allows the public health endpoint %s", (path) => {
    expect(isPublicBackendHealthPath(path)).toBe(true);
  });

  it.each([
    ["api", "v1", "auth", "me"],
    ["api", "v1", "tutor", "capabilities"],
    ["livez", "details"],
    [],
  ])("keeps non-health backend paths protected: %j", (path) => {
    expect(isPublicBackendHealthPath(path)).toBe(false);
  });
});
