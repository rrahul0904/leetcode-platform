import { describe, expect, it } from "vitest";

import { resolveBackendOrigin } from "./backend-origin";

describe("resolveBackendOrigin", () => {
  it("accepts a public HTTPS production backend", () => {
    expect(
      resolveBackendOrigin("https://api.skillforge.example/", "production"),
    ).toBe("https://api.skillforge.example");
  });

  it("allows Vercel internal HTTP service URLs in production", () => {
    expect(
      resolveBackendOrigin(
        "http://skillforge-api.vercel.internal",
        "production",
      ),
    ).toBe("http://skillforge-api.vercel.internal");
  });

  it.each([
    "http://localhost:8002",
    "https://localhost",
    "https://api.localhost",
    "http://127.0.0.1:8002",
    "https://127.12.1.4",
    "http://0.0.0.0:8002",
    "https://[::1]",
  ])("rejects production loopback backend %s", (origin) => {
    expect(() => resolveBackendOrigin(origin, "production")).toThrow(
      /localhost|loopback/,
    );
  });

  it("rejects public plain HTTP backends in production", () => {
    expect(() =>
      resolveBackendOrigin("http://api.skillforge.example", "production"),
    ).toThrow(/HTTPS/);
  });

  it("allows localhost during non-production development", () => {
    expect(
      resolveBackendOrigin("http://localhost:8002", "development"),
    ).toBe("http://localhost:8002");
  });

  it.each(["ftp://api.example.com", "not-a-url"])(
    "rejects non HTTP(S) or malformed backend %s",
    (origin) => {
      expect(() => resolveBackendOrigin(origin, "production")).toThrow(
        /HTTP\(S\)/,
      );
    },
  );
});
