/** First-party examples; repository-history RE-292 is a collision alias, not the tracker row. */
export type TypingLanguage = "python" | "sql" | "javascript";
export type TypingSnippet = {
  schemaVersion: 1;
  id: string;
  version: number;
  language: TypingLanguage;
  topic: string;
  difficulty: "intro" | "intermediate";
  expectedText: string;
  indentation: 2 | 4;
  provenance: string;
  license: string;
  deprecated: boolean;
};
const provenance = "First-party, project-authored Rigor teaching text in the Code Typing implementation (2026-09-27); no donor snippets, source files, assets, or branding were used.";
const license = "Original project work; repository has no standalone license file, so these examples are limited to this product pending an explicit public content license.";
export const SNIPPETS: readonly TypingSnippet[] = [
  {
    schemaVersion: 1, id: "py-indexed-total", version: 1, language: "python",
    topic: "Loops and accumulation", difficulty: "intro", indentation: 4,
    expectedText: "def indexed_total(values):\n    total = 0\n    for index, value in enumerate(values):\n        total += index + value\n    return total",
    provenance, license, deprecated: false,
  },
  {
    schemaVersion: 1, id: "py-label-cleanup", version: 1, language: "python",
    topic: "Filtering and strings", difficulty: "intermediate", indentation: 4,
    expectedText: 'def clean_labels(records):\n    return [row["label"].strip() for row in records if row.get("label")]',
    provenance, license, deprecated: false,
  },
  {
    schemaVersion: 1, id: "sql-region-count", version: 1, language: "sql",
    topic: "Grouping with a CTE", difficulty: "intermediate", indentation: 2,
    expectedText: "WITH grouped AS (\n  SELECT region, COUNT(*) AS order_count\n  FROM sample_orders\n  GROUP BY region\n)\nSELECT region, order_count\nFROM grouped\nORDER BY order_count DESC;",
    provenance, license, deprecated: false,
  },
  {
    schemaVersion: 1, id: "sql-category-mean", version: 1, language: "sql",
    topic: "Filtering and averages", difficulty: "intro", indentation: 2,
    expectedText: "SELECT category, AVG(unit_price) AS mean_price\nFROM demo_inventory\nWHERE units_available > 0\nGROUP BY category\nORDER BY category;",
    provenance, license, deprecated: false,
  },
  {
    schemaVersion: 1, id: "js-reduce-amounts", version: 1, language: "javascript",
    topic: "Array reduction", difficulty: "intro", indentation: 2,
    expectedText: "function sumAmounts(items) {\n  return items.reduce((sum, item) => sum + item.amount, 0);\n}",
    provenance, license, deprecated: false,
  },
  {
    schemaVersion: 1, id: "js-filter-names", version: 1, language: "javascript",
    topic: "Array transformations", difficulty: "intermediate", indentation: 2,
    expectedText: "const activeNames = rows\n  .filter((row) => row.enabled)\n  .map((row) => row.name.trim());",
    provenance, license, deprecated: false,
  },
];
export const LANGUAGES: readonly TypingLanguage[] = ["python", "sql", "javascript"];
export const DURATIONS = [30, 60, 120] as const;
export function snippetsFor(language: TypingLanguage) {
  return SNIPPETS.filter((snippet) => snippet.language === language && !snippet.deprecated);
}
export function snippetLength(snippet: TypingSnippet): number {
  return Array.from(snippet.expectedText).length;
}
