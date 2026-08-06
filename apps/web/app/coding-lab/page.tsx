"use client";

import { useState } from "react";

import {
  type CodingLanguage,
  type CodingPadResult,
  InteractiveCodingPad,
} from "@/components/interactive-coding-pad";

const pythonStarter = `def longest_unique_substring(value: str) -> int:
    # Return the longest substring length without repeated characters.
    pass
`;

const sqlStarter = `SELECT
  date_trunc('month', signup_date) AS cohort_month,
  count(*) AS users
FROM users
GROUP BY 1
ORDER BY 1;
`;

const sqlSchema =
  "users\n  user_id bigint primary key\n  signup_date timestamptz not null";

async function simulatedRun(
  language: CodingLanguage,
  source: string,
): Promise<CodingPadResult> {
  await new Promise((resolve) => window.setTimeout(resolve, 450));
  const passes =
    language === "python"
      ? source.includes("return") && !source.includes("pass\n")
      : source.trim().toLowerCase().startsWith("select");
  return passes
    ? {
        status: "passed",
        message:
          language === "python"
            ? "3 of 3 public tests passed."
            : "Query completed and returned the expected columns.",
        runtimeMs: language === "python" ? 38 : 21,
        ...(language === "sql"
          ? {
              rows: [
                { cohort_month: "2026-01-01", users: 142 },
                { cohort_month: "2026-02-01", users: 167 },
              ],
            }
          : {}),
      }
    : {
        status: "failed",
        message:
          language === "python"
            ? "The starter implementation still returns no result."
            : "The query must begin with a read-only SELECT statement.",
      };
}

export default function CodingLabPage() {
  const [language, setLanguage] = useState<CodingLanguage>("python");
  const python = language === "python";
  const codingPadProps = python ? {} : { schema: sqlSchema };

  return (
    <div className="coding-lab-page">
      <header>
        <div>
          <span className="kb-eyebrow">INTERACTIVE CODING LAB</span>
          <h1>{python ? "Python interview workspace" : "SQL analytics workspace"}</h1>
          <p>
            This vertical slice proves the editor behavior, draft recovery, custom tests,
            output rendering, SQL result grids, reset, full-screen mode, and keyboard shortcuts.
            Repository execution integration remains protected by the existing publication gate.
          </p>
        </div>
        <div className="coding-lab-page__modes" aria-label="Coding language">
          <button
            className={python ? "is-active" : ""}
            onClick={() => setLanguage("python")}
            type="button"
          >
            Python
          </button>
          <button
            className={!python ? "is-active" : ""}
            onClick={() => setLanguage("sql")}
            type="button"
          >
            SQL
          </button>
        </div>
      </header>

      <div className="coding-lab-page__grid">
        <article className="coding-lab-page__prompt">
          <span className="kb-difficulty kb-difficulty--medium">Intermediate</span>
          <h2>{python ? "Longest unique substring" : "Monthly signup cohorts"}</h2>
          <p>
            {python
              ? "Return the length of the longest substring that contains no repeated characters."
              : "Aggregate users into monthly signup cohorts and return each cohort with its user count."}
          </p>
          <h3>Example</h3>
          <pre>
            {python
              ? 'Input: "abcabcbb"\nOutput: 3'
              : "users(user_id, signup_date)\nExpected columns: cohort_month, users"}
          </pre>
          <h3>Constraints</h3>
          <ul>
            {python ? (
              <>
                <li>Input length may reach 100,000 characters.</li>
                <li>Target O(n) time and O(k) auxiliary space.</li>
              </>
            ) : (
              <>
                <li>Use PostgreSQL 18 syntax.</li>
                <li>The candidate role is read-only.</li>
              </>
            )}
          </ul>
        </article>

        <InteractiveCodingPad
          key={language}
          questionKey={python ? "demo-longest-unique" : "demo-cohort-months"}
          language={language}
          initialSource={python ? pythonStarter : sqlStarter}
          executionEnabled
          {...codingPadProps}
          onRun={(source) => simulatedRun(language, source)}
          onSubmit={(source) => simulatedRun(language, source)}
        />
      </div>
    </div>
  );
}
