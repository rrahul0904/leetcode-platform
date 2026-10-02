import { describe, expect, it } from "vitest";

import nextConfig from "./next.config";

describe("Next.js route redirects", () => {
  it("keeps the authenticated workspace route available as a page", async () => {
    const redirects = await nextConfig.redirects?.();

    expect(redirects?.some(({ source }) => source === "/workspace")).toBe(false);
  });
});
