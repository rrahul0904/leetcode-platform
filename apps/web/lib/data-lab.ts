/**
 * Original, deterministic browser-only medallion exercise.
 * No network calls, eval, durable writes or remote execution.
 * Amounts remain integer cents and are NEVER summed across currencies.
 */
export const DATA_LAB_MAX_BYTES = 65_536;
export const DATA_LAB_MAX_RECORDS = 500;
const MAX_CELL_LENGTH = 4_096;
const HEADERS = ["order_id", "customer_id", "order_date", "amount", "currency"] as const;
const CURRENCIES = new Set(["USD", "EUR", "GBP"]);

export const DATA_LAB_EXAMPLE = [
  "order_id,customer_id,order_date,amount,currency",
  "ORD-1001,CUST-01,2026-10-20,49.99,USD",
  "ORD-1002,CUST-02,2026-10-20,19.50,USD",
  "ORD-1002,CUST-02,2026-10-20,19.50,USD",
  "ORD-1003,CUST-03,2026-10-21,15.00,EUR",
  "ORD-1004,CUST-04,2026-10-21,-3.00,USD",
  "ORD-1005,CUST-05,2026-02-30,12.00,GBP",
].join("\n");

export class DataLabInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DataLabInputError";
  }
}

export type BronzeRecord = {
  record: number;
  fields: string[];
};

export type SilverOrder = {
  record: number;
  orderId: string;
  customerId: string;
  orderDate: string;
  amountCents: number;
  currency: string;
};

export type QuarantineRecord = BronzeRecord & { reason: string };

export type GoldDailyTotal = {
  date: string;
  currency: string;
  orders: number;
  amountCents: number;
};

export type DataLabResult = {
  bronze: BronzeRecord[];
  silver: SilverOrder[];
  quarantine: QuarantineRecord[];
  gold: GoldDailyTotal[];
  metrics: {
    received: number;
    accepted: number;
    quarantined: number;
    duplicates: number;
  };
};

function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let closedQuote = false;

  function append(value: string) {
    field += value;
    if (field.length > MAX_CELL_LENGTH) {
      throw new DataLabInputError("A CSV field exceeds the 4,096-character safety limit.");
    }
  }

  function endField() {
    row.push(field);
    field = "";
    closedQuote = false;
  }

  function endRow() {
    endField();
    rows.push(row);
    row = [];
    if (rows.length > DATA_LAB_MAX_RECORDS + 1) {
      throw new DataLabInputError("Maximum 500 data records per run. Reduce the input.");
    }
  }

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (quoted) {
      if (char === '"') {
        if (source[index + 1] === '"') {
          append('"');
          index += 1;
        } else {
          quoted = false;
          closedQuote = true;
        }
      } else {
        append(char);
      }
      continue;
    }
    if (char === ",") {
      endField();
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[index + 1] === "\n") index += 1;
      endRow();
    } else if (char === '"' && field.length === 0 && !closedQuote) {
      quoted = true;
    } else if (char === '"' || closedQuote) {
      throw new DataLabInputError("Malformed CSV quoting. Double quotes inside quoted fields.");
    } else {
      append(char);
    }
  }
  if (quoted) throw new DataLabInputError("Unterminated quoted CSV field.");
  if (field.length > 0 || row.length > 0 || closedQuote) endRow();
  return rows;
}

function isActualIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  if (year < 1900 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) return false;
  const actual = new Date(Date.UTC(year, month - 1, day));
  return (
    actual.getUTCFullYear() === year &&
    actual.getUTCMonth() === month - 1 &&
    actual.getUTCDate() === day
  );
}

function parseCents(value: string): number | null {
  const match = /^(\d{1,8})(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) return null;
  const cents = Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
  return cents > 0 && Number.isSafeInteger(cents) ? cents : null;
}

function validate(record: BronzeRecord): SilverOrder | string {
  if (record.fields.length !== HEADERS.length) return "Expected exactly five CSV columns.";
  const [orderId, customerId, orderDate, amount, currency] = record.fields.map((s) => s.trim());
  const identifier = /^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/;
  if (!identifier.test(orderId)) return "Invalid order_id (1–40 letters, digits, _ or -).";
  if (!identifier.test(customerId)) return "Invalid customer_id (1–40 letters, digits, _ or -).";
  if (!isActualIsoDate(orderDate)) return "Invalid order_date (real YYYY-MM-DD required).";
  const amountCents = parseCents(amount);
  if (amountCents === null) return "Invalid positive amount (up to 8 digits and 2 decimals).";
  if (!CURRENCIES.has(currency)) return "Unsupported currency (USD, EUR or GBP required).";
  return { record: record.record, orderId, customerId, orderDate, amountCents, currency };
}

export function runDataLab(csv: string): DataLabResult {
  if (new TextEncoder().encode(csv).byteLength > DATA_LAB_MAX_BYTES) {
    throw new DataLabInputError("Input exceeds the 64 KiB budget. Reduce the CSV.");
  }
  const rows = parseCsv(csv.replace(/^\uFEFF/, ""));
  if (rows.length === 0) {
    throw new DataLabInputError("Enter a CSV header and up to 500 data records.");
  }
  if (
    rows[0].length !== HEADERS.length ||
    rows[0].some((value, index) => value.trim() !== HEADERS[index])
  ) {
    throw new DataLabInputError("Header must be: order_id,customer_id,order_date,amount,currency");
  }

  const bronze: BronzeRecord[] = [];
  const silver: SilverOrder[] = [];
  const quarantine: QuarantineRecord[] = [];
  const seen = new Set<string>();
  let duplicates = 0;
  const aggregates = new Map<string, GoldDailyTotal>();
  for (const [index, fields] of rows.slice(1).entries()) {
    if (fields.length === 1 && fields[0].trim() === "") continue;
    const record: BronzeRecord = { record: index + 2, fields };
    bronze.push(record);
    const outcome = validate(record);
    if (typeof outcome === "string") {
      quarantine.push({ ...record, reason: outcome });
      continue;
    }
    if (seen.has(outcome.orderId)) {
      duplicates += 1;
      quarantine.push({ ...record, reason: "Duplicate order_id; first valid record kept." });
      continue;
    }
    seen.add(outcome.orderId);
    silver.push(outcome);
    const key = outcome.orderDate + "|" + outcome.currency;
    const total = aggregates.get(key) ?? {
      date: outcome.orderDate, currency: outcome.currency, orders: 0, amountCents: 0,
    };
    total.orders += 1;
    total.amountCents += outcome.amountCents;
    aggregates.set(key, total);
  }
  const gold = [...aggregates.values()].sort(
    (a, b) => a.date.localeCompare(b.date) || a.currency.localeCompare(b.currency),
  );
  return {
    bronze,
    silver,
    quarantine,
    gold,
    metrics: {
      received: bronze.length,
      accepted: silver.length,
      quarantined: quarantine.length,
      duplicates,
    },
  };
}

export function formatCents(cents: number, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}
