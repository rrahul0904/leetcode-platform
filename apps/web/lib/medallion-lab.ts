// Independently authored browser-only exercise: no network, persistence or code execution.
export const SAMPLE_ORDERS = `event_id,order_id,order_ts,sku,quantity,unit_price_usd
arr-01,order-101,2026-10-01T09:00:00Z,BOOK,2,12.50
arr-02,order-102,2026-10-01T09:30:00Z,PEN,3,2.00
arr-02,order-102,2026-10-01T09:30:00Z,PEN,3,2.00
arr-03,order-103,2026-10-02T10:00:00Z,BOOK,1,12.50
arr-04,order-104,2026-10-02T10:30:00Z,PEN,-1,2.00`;

const COLUMNS = ["event_id", "order_id", "order_ts", "sku", "quantity", "unit_price_usd"] as const;
const MAX_SOURCE_BYTES = 100_000;
const MAX_ROWS = 500;

type SourceColumn = (typeof COLUMNS)[number];
export type RawOrder = Record<SourceColumn, string> & { line: number };
export type CleanOrder = {
  eventId: string;
  orderId: string;
  day: string;
  sku: string;
  quantity: number;
  unitPriceCents: number;
  totalCents: number;
};
export type GoldMetric = {
  day: string;
  sku: string;
  orders: number;
  units: number;
  revenueCents: number;
};
export type RejectedOrder = { line: number; eventId: string; reason: string };
export type PipelineResult = {
  bronze: RawOrder[];
  silver: CleanOrder[];
  gold: GoldMetric[];
  quarantined: RejectedOrder[];
  duplicates: number;
  errors: string[];
};

// Bounded RFC4180-style CSV reader with escaped quotes and quoted newlines.
function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let fields: string[] = [];
  let value = "";
  let mode: "start" | "plain" | "quoted" | "closed" = "start";
  const finishCell = () => {
    fields.push(value);
    value = "";
    mode = "start";
  };
  const finishRow = () => {
    finishCell();
    if (fields.some((item) => item.trim() !== "")) rows.push(fields);
    fields = [];
  };
  const normalized = source.replace(/\r\n?/g, "\n");
  for (let index = 0; index < normalized.length; index += 1) {
    const ch = normalized[index];
    if (mode === "quoted") {
      if (ch === '"') {
        if (normalized[index + 1] === '"') {
          value += '"';
          index += 1;
        } else {
          mode = "closed";
        }
      } else {
        value += ch;
      }
    } else if (ch === "," || ch === "\n") {
      if (ch === ",") finishCell();
      else finishRow();
    } else if (ch === '"' && mode === "start") {
      mode = "quoted";
    } else if (mode === "closed" && (ch === " " || ch === "\t")) {
      // Trailing whitespace after a closing quote is harmless.
    } else if (ch === '"' || mode === "closed") {
      throw new Error("Invalid CSV quoting");
    } else {
      mode = "plain";
      value += ch;
    }
  }
  if (mode === "quoted") throw new Error("Unterminated CSV quote");
  if (fields.length > 0 || value.length > 0 || mode === "closed") finishRow();
  return rows;
}

function getCents(value: string): number | null {
  if (!/^(0|[1-9]\d{0,5})(?:\.\d{1,2})?$/.test(value)) return null;
  const [dollars, fraction = ""] = value.split(".");
  const result = Number(dollars) * 100 + Number(fraction.padEnd(2, "0"));
  return result <= 10_000_000 ? result : null;
}

function utcDay(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return null;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return null;
  return new Date(timestamp).toISOString() === value.replace("Z", ".000Z")
    ? value.slice(0, 10)
    : null;
}

export function runMedallionLab(source: string): PipelineResult {
  const report: PipelineResult = {
    bronze: [], silver: [], gold: [], quarantined: [], duplicates: 0, errors: [],
  };
  if (new TextEncoder().encode(source).length > MAX_SOURCE_BYTES) {
    report.errors.push(`Input exceeds ${MAX_SOURCE_BYTES} bytes`);
    return report;
  }
  let rows: string[][];
  try {
    rows = parseCsv(source);
  } catch (error) {
    report.errors.push(error instanceof Error ? error.message : "CSV parse failed");
    return report;
  }
  if (rows.length === 0) {
    report.errors.push("A header and at least one data row are required");
    return report;
  }
  const header = rows[0]!.map((cell) => cell.trim());
  if (
    header.length !== COLUMNS.length ||
    new Set(header).size !== COLUMNS.length ||
    COLUMNS.some((key) => !header.includes(key))
  ) {
    report.errors.push(`Expected exactly these columns: ${COLUMNS.join(", ")}`);
    return report;
  }
  if (rows.length < 2) {
    report.errors.push("Add at least one order below the header");
    return report;
  }
  if (rows.length - 1 > MAX_ROWS) {
    report.errors.push(`Input exceeds ${MAX_ROWS} data rows`);
    return report;
  }
  const columnIndex = Object.fromEntries(header.map((key, index) => [key, index])) as Record<SourceColumn, number>;
  const seen = new Map<string, string>();
  for (const [index, fields] of rows.slice(1).entries()) {
    const line = index + 2;
    const record = Object.fromEntries(
      COLUMNS.map((key) => [key, (fields[columnIndex[key]] || "").trim()]),
    ) as Record<SourceColumn, string>;
    const raw = { ...record, line };
    report.bronze.push(raw);
    const reject = (reason: string) => {
      report.quarantined.push({ line, eventId: raw.event_id, reason });
    };
    if (fields.length !== COLUMNS.length) {
      reject("Incorrect column count");
      continue;
    }
    if (!/^[a-zA-Z0-9_-]{1,40}$/.test(raw.event_id) ||
        !/^[a-zA-Z0-9_-]{1,40}$/.test(raw.order_id) ||
        !/^[a-zA-Z0-9_-]{1,40}$/.test(raw.sku)) {
      reject("Event, order and SKU identifiers are required (letters, digits, _ or -)");
      continue;
    }
    const fingerprint = JSON.stringify(COLUMNS.map((key) => raw[key]));
    const earlier = seen.get(raw.event_id);
    if (earlier !== undefined) {
      if (earlier === fingerprint) report.duplicates += 1;
      else reject("Conflicting payload for an existing event_id");
      continue;
    }
    const day = utcDay(raw.order_ts);
    const quantity = Number(raw.quantity);
    const unitPriceCents = getCents(raw.unit_price_usd);
    if (!day) reject("Invalid UTC timestamp");
    else if (!/^\d+$/.test(raw.quantity) || !Number.isSafeInteger(quantity) || quantity < 1 || quantity > 1000) {
      reject("Quantity must be an integer from 1 to 1000");
    } else if (unitPriceCents === null) {
      reject("Unit price must be USD from 0.00 to 100000.00 with at most 2 decimals");
    } else {
      seen.set(raw.event_id, fingerprint);
      report.silver.push({
        eventId: raw.event_id, orderId: raw.order_id, day, sku: raw.sku,
        quantity, unitPriceCents, totalCents: quantity * unitPriceCents,
      });
    }
  }
  const grouped = new Map<string, GoldMetric>();
  for (const order of report.silver) {
    const key = JSON.stringify([order.day, order.sku]);
    const metric = grouped.get(key) ?? {
      day: order.day, sku: order.sku, orders: 0, units: 0, revenueCents: 0,
    };
    metric.orders += 1;
    metric.units += order.quantity;
    metric.revenueCents += order.totalCents;
    grouped.set(key, metric);
  }
  report.gold = [...grouped.values()].sort((a, b) =>
    a.day.localeCompare(b.day) || a.sku.localeCompare(b.sku),
  );
  return report;
}