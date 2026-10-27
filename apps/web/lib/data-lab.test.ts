import { describe, expect, it } from "vitest";

import {
  DATA_LAB_EXAMPLE,
  DataLabInputError,
  runDataLab,
  formatCents,
} from "./data-lab";

describe("original medallion data engineering lab", () => {
  it("replays deterministically, deduplicates and quarantines invalid rows", () => {
    const first = runDataLab(DATA_LAB_EXAMPLE);
    const second = runDataLab(DATA_LAB_EXAMPLE);
    expect(first).toEqual(second);
    expect(first.metrics).toEqual({
      received: 6,
      accepted: 3,
      quarantined: 3,
      duplicates: 1,
    });
    expect(first.silver.map((order) => order.orderId)).toEqual([
      "ORD-1001", "ORD-1002", "ORD-1003",
    ]);
    expect(first.gold).toEqual([
      { date: "2026-10-20", currency: "USD", orders: 2, amountCents: 6949 },
      { date: "2026-10-21", currency: "EUR", orders: 1, amountCents: 1500 },
    ]);
    expect(first.quarantine.map((row) => row.reason)).toEqual([
      "Duplicate order_id; first valid record kept.",
      "Invalid positive amount (up to 8 digits and 2 decimals).",
      "Invalid order_date (real YYYY-MM-DD required).",
    ]);
  });

  it("never combines amounts across currencies", () => {
    const result = runDataLab([
      "order_id,customer_id,order_date,amount,currency",
      "o1,c1,2026-01-01,1.01,USD",
      "o2,c2,2026-01-01,2.02,EUR",
    ].join("\n"));
    expect(result.gold).toEqual([
      { date: "2026-01-01", currency: "EUR", orders: 1, amountCents: 202 },
      { date: "2026-01-01", currency: "USD", orders: 1, amountCents: 101 },
    ]);
    expect(formatCents(101, "USD")).toBe("$1.01");
  });

  it("supports BOM, quoted fields, escaped quotes, and CRLF while rejecting unsafe values", () => {
    const result = runDataLab(
      '\uFEFForder_id,customer_id,order_date,amount,currency\r\n' +
      '"a1","user,2",2026-01-01,0.01,USD\r\n' +
      '"a2","user""2",2026-01-02,2.00,USD\r\n' +
      "a3,valid_user,2026-01-03,1,GBP\r\n",
    );
    expect(result.metrics.accepted).toBe(1);
    expect(result.metrics.quarantined).toBe(2);
    expect(result.quarantine.every((row) => row.reason.startsWith("Invalid customer_id"))).toBe(true);
  });

  it("handles header-only and blank lines without inventing transactions", () => {
    const result = runDataLab("order_id,customer_id,order_date,amount,currency\n\n");
    expect(result.metrics).toEqual({
      received: 0, accepted: 0, quarantined: 0, duplicates: 0,
    });
    expect(result.gold).toEqual([]);
  });

  it("fails on malformed headers and quote structures", () => {
    expect(() => runDataLab("")).toThrow(DataLabInputError);
    expect(() => runDataLab("order_id,amount\nx,1")).toThrow(/Header must be/);
    expect(() => runDataLab('order_id,customer_id,order_date,amount,currency\n"a1,c1,2026-01-01,1,USD'))
      .toThrow(/Unterminated quoted/);
    expect(() => runDataLab('order_id,customer_id,order_date,amount,currency\nab"cd,c1,2026-01-01,1,USD'))
      .toThrow(/Malformed CSV quoting/);
  });

  it("quarantines invalid currency, dates, zero values, identifiers and wrong column counts", () => {
    const result = runDataLab([
      "order_id,customer_id,order_date,amount,currency",
      "o1,c1,2026-03-01,1.00,JPY",
      "o2,c2,2026-02-29,1.00,USD",
      "o3,c3,2026-03-01,0,USD",
      "o 4,c4,2026-03-01,3.00,USD",
      "o5,c5,2026-03-01,3.00",
      "o6,c6,2026-03-01,3.001,USD",
    ].join("\n"));
    expect(result.metrics).toEqual({
      received: 6, accepted: 0, quarantined: 6, duplicates: 0,
    });
  });

  it("uses first VALID occurrence for deduplication", () => {
    const result = runDataLab([
      "order_id,customer_id,order_date,amount,currency",
      "o1,c1,not-a-date,2,USD",
      "o1,c1,2026-03-01,2,USD",
      "o1,c1,2026-03-01,3,USD",
    ].join("\n"));
    expect(result.silver).toHaveLength(1);
    expect(result.silver[0].amountCents).toBe(200);
    expect(result.metrics.duplicates).toBe(1);
  });

  it("enforces byte, record and field budgets", () => {
    const header = "order_id,customer_id,order_date,amount,currency";
    expect(() => runDataLab(header + "\n" + "😀".repeat(17000)))
      .toThrow(/64 KiB budget/);
    expect(() => runDataLab(header + "\n" + "x".repeat(4100)))
      .toThrow(/CSV field exceeds/);
    const rows = Array.from({ length: 501 }, (_, index) => "o" + index + ",c,2026-01-01,1,USD");
    expect(() => runDataLab([header, ...rows].join("\n")))
      .toThrow(/Maximum 500/);
    const atLimit = runDataLab([header, ...rows.slice(0, 500)].join("\n"));
    expect(atLimit.metrics.accepted).toBe(500);
  });
});
