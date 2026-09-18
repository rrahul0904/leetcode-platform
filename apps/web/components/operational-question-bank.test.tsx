import { describe, expect, it } from "vitest";

import { availabilityLabel } from "@/components/operational-question-bank";

describe("availabilityLabel", () => {
  it("uses explicit candidate-facing availability language", () => {
    expect(availabilityLabel("runnable")).toBe("Runnable");
    expect(availabilityLabel("hosted")).toBe("Hosted");
    expect(availabilityLabel("in_review")).toBe("In review");
    expect(availabilityLabel("reference_only")).toBe("Reference only");
  });
});
