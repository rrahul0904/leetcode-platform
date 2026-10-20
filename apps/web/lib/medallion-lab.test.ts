import { describe, expect, it } from "vitest";
import { runMedallionLab, SAMPLE_ORDERS } from "./medallion-lab";

const HEADER = "event_id,order_id,order_ts,sku,quantity,unit_price_usd";
const LINE = "a1,o1,2026-10-01T09:00:00Z,BOOK,2,12.50";
function single(value = LINE) { return runMedallionLab(`${HEADER}\n${value}`); }

describe("original medallion practice engine", () => {
  it("calculates Bronze, Silver, Gold and quarantine from the editable sample", () => {
    const result = runMedallionLab(SAMPLE_ORDERS);
    expect(result.errors).toEqual([]);
    expect(result.bronze).toHaveLength(5);
    expect(result.silver).toHaveLength(3);
    expect(result.duplicates).toBe(1);
    expect(result.quarantined).toEqual([{ line: 6, eventId: "arr-04", reason: "Quantity must be an integer from 1 to 1000" }]);
    expect(result.gold).toEqual([
      { day: "2026-10-01", sku: "BOOK", orders: 1, units: 2, revenueCents: 2500 },
      { day: "2026-10-01", sku: "PEN", orders: 1, units: 3, revenueCents: 600 },
      { day: "2026-10-02", sku: "BOOK", orders: 1, units: 1, revenueCents: 1250 },
    ]);
  });
  it("passes the gate after the learner repairs quarantined source data", () => {
    const fixed = runMedallionLab(SAMPLE_ORDERS.replace("PEN,-1,2.00", "PEN,1,2.00"));
    expect(fixed.quarantined).toHaveLength(0);
    expect(fixed.silver).toHaveLength(4);
    expect(fixed.gold).toHaveLength(4);
  });
  it("deduplicates identical events but quarantines conflicts", () => {
    const exact = runMedallionLab(`${HEADER}\n${LINE}\n${LINE}`);
    expect(exact.duplicates).toBe(1);
    expect(exact.silver).toHaveLength(1);
    const mismatch = runMedallionLab(`${HEADER}\n${LINE}\n${LINE.replace(",2,", ",3,")}`);
    expect(mismatch.duplicates).toBe(0);
    expect(mismatch.silver).toHaveLength(1);
    expect(mismatch.quarantined[0].reason).toMatch(/Conflicting/);
  });
  it("rejects invalid timestamps, quantities, prices and IDs", () => {
    expect(single(LINE.replace("2026-10-01", "2026-02-30")).quarantined[0].reason).toMatch(/timestamp/);
    expect(single(LINE.replace(",2,12", ",0,12")).quarantined[0].reason).toMatch(/Quantity/);
    expect(single(LINE.replace("12.50", "12.999")).quarantined[0].reason).toMatch(/Unit price/);
    expect(single(LINE.replace("a1,", "bad id,")).quarantined[0].reason).toMatch(/identifiers/);
  });
  it("rejects structurally invalid CSV, empty inputs, and unsupported headers", () => {
    expect(runMedallionLab("").errors[0]).toMatch(/header/);
    expect(runMedallionLab(HEADER).errors[0]).toMatch(/Add at least/);
    expect(runMedallionLab("event_id,event_id\na,b").errors[0]).toMatch(/Expected exactly/);
    expect(runMedallionLab(`${HEADER}\n"unterminated`).errors[0]).toMatch(/Unterminated/);
    expect(runMedallionLab(`${HEADER}\n"closed"oops`).errors[0]).toMatch(/quoting/);
  });
  it("supports escaped quotes without accepting malformed row widths", () => {
    const quoted = single(LINE.replace("BOOK", '"BOOK"'));
    expect(quoted.silver[0].sku).toBe("BOOK");
    const escaped = single(LINE.replace("BOOK", '"BO""OK"'));
    expect(escaped.quarantined[0].reason).toMatch(/identifiers/);
    const mismatch = single(`${LINE},extra`);
    expect(mismatch.quarantined[0].reason).toMatch(/column count/);
  });
  it("applies bounded resource limits", () => {
    expect(runMedallionLab("x".repeat(100_001)).errors[0]).toMatch(/bytes/);
    expect(runMedallionLab([HEADER, ...Array.from({ length: 501 }, (_, i) => LINE.replace("a1", `a${i}`))].join("\n")).errors[0]).toMatch(/500/);
  });
  it("returns an identical report for identical input", () => {
    expect(runMedallionLab(SAMPLE_ORDERS)).toEqual(runMedallionLab(SAMPLE_ORDERS));
  });
});