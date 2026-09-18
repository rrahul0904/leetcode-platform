import { describe, expect, it } from "vitest";

import { learningPaths, mockFocuses, tracks } from "./product-data";

describe("DataForge consolidation", () => {
  it("exposes data engineering as a first-class technical learning track", () => {
    expect(tracks).toContainEqual(["data-engineering", "Data engineering"]);
    const path = learningPaths.find((item) => item.id === "data-engineering-interviews");
    expect(path).toBeDefined();
    expect(path?.tracks).toContain("data-engineering");
    expect(path?.tracks).toContain("sql-analytics");
    expect(path?.tracks).toContain("python-engineering");
    expect(mockFocuses).toContainEqual(
      expect.objectContaining({
        id: "data",
        track: "data-engineering",
      }),
    );
  });
});
