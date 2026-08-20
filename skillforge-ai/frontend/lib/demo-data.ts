export type DemoQuestion = {
  id: string; title: string; difficulty: "Easy"|"Medium"|"Hard"; type: string; topic: string; bank: string; description: string; language: string; solution: string; explanation: string; tags: string[];
};

export const demoQuestions: DemoQuestion[] = [
  {
    "id": "PY-EAS-0001",
    "title": "Arrays / Iteration · Given a list of integer duration values, return the sum of values divisible by 3 and greater than or equal to 11",
    "difficulty": "Easy",
    "type": "Coding",
    "topic": "Python",
    "bank": "python",
    "description": "### Question\nGiven a list of integer duration values, return the sum of values divisible by 3 and greater than or equal to 11.\n\n### Context\nUse this in a insurance data-processing service. Inputs may contain duplicates and boundary values.\n\n### Constraints\n- Input size may reach 200,000 elements unless the problem structure implies a smaller bound.\n- Do not rely on external services.",
    "language": "python",
    "solution": "def solve(values, d, t):\n    return sum(x for x in values if x % d == 0 and x >= t)",
    "explanation": "### Source Expected Approach\nFiltered Aggregate: identify the governing invariant and choose the data structure implied by the subtopic.\n\n\n---\n\n### Working Python Solution\n```python\ndef solve(values, d, t):\n    return sum(x for x in values if x % d == 0 and x >= t)\n```\n\n### Explanation\nFilter while aggregating; no auxiliary list is required.\n\n### Complexity\n- Time: **O(n)**\n- Space: **O(1)**\n\n### Common Mistakes\n- Ignoring empty inputs or duplicate values.\n- Using a brute-force nested scan when the stated technique gives a better bound.\n- Mishandling inclusive/exclusive boundaries.\n\n### Tags\npython, arrays, iteration, insurance\n\n\n---",
    "tags": ["arrays-iteration","coding","python"]
  },
  {
    "id": "PY-EAS-0002",
    "title": "Hash Map · Given a sequence of patient ids, return the IDs appearing at least 4 times, sorted lexicographically",
    "difficulty": "Easy",
    "type": "Coding",
    "topic": "Python",
    "bank": "python",
    "description": "### Question\nGiven a sequence of patient_ids, return the IDs appearing at least 4 times, sorted lexicographically.\n\n### Context\nUse this in a healthcare data-processing service. Inputs may contain duplicates and boundary values.\n\n### Constraints\n- Input size may reach 200,000 elements unless the problem structure implies a smaller bound.\n- Do not rely on external services.",
    "language": "python",
    "solution": "from collections import Counter\ndef solve(ids, k):\n    c = Counter(ids)\n    return sorted([x for x,n in c.items() if n >= k])",
    "explanation": "### Source Expected Approach\nFrequency Threshold: identify the governing invariant and choose the data structure implied by the subtopic.\n\n### Working Python Solution\n```python\nfrom collections import Counter\ndef solve(ids, k):\n    c = Counter(ids)\n    return sorted([x for x,n in c.items() if n >= k])\n```\n\n### Explanation\nCount frequencies, then sort only qualifying unique IDs.\n\n### Complexity\n- Time: **O(n + u log u)**\n- Space: **O(u)**",
    "tags": ["coding","hash-map","python"]
  },
  {
    "id": "SQL-EAS-0001",
    "title": "GROUP BY · Return total duration and row count per carrier id for completed rows",
    "difficulty": "Easy",
    "type": "SQL Coding",
    "topic": "SQL",
    "bank": "sql_leetcode",
    "description": "### Business Context\nA logistics analytics team stores shipments in a warehouse.\n\n### Question\nReturn total duration and row count per carrier_id for completed rows.\n\n### Schema\n```sql\nCREATE TABLE facts (fact_id BIGINT, carrier_id BIGINT, category_id BIGINT, event_ts TIMESTAMP, ingest_seq BIGINT, region VARCHAR(20), status VARCHAR(20), duration DECIMAL(18,2));\n```\n\n### Sample Data\n| fact_id | carrier_id | event_ts | region | status | duration |\n|---:|---:|---|---|---|---:|\n| 1 | 101 | 2026-01-01 09:00 | NA | completed | 120 |\n| 2 | 101 | 2026-01-02 10:00 | EMEA | active | 80 |\n| 3 | 202 | 2026-01-03 11:00 | NA | completed | 150 |",
    "language": "sql",
    "solution": "SELECT carrier_id, SUM(duration) AS total_duration, COUNT(*) AS row_count\nFROM facts\nWHERE status='completed'\nGROUP BY carrier_id;",
    "explanation": "### Final SQL\n```sql\nSELECT carrier_id, SUM(duration) AS total_duration, COUNT(*) AS row_count\nFROM facts\nWHERE status='completed'\nGROUP BY carrier_id;\n```\n\n### Explanation\nAggregation is the primary pattern. The query is written in ANSI/PostgreSQL-style SQL.",
    "tags": ["group-by","sql","sql-coding","sql-leetcode"]
  },
  {
    "id": "SQL-EAS-0002",
    "title": "WHERE · Return rows from region 'APAC' with latency = 102, newest first",
    "difficulty": "Easy",
    "type": "SQL Coding",
    "topic": "SQL",
    "bank": "sql_leetcode",
    "description": "### Business Context\nA energy analytics team stores meter readings in a warehouse.\n\n### Question\nReturn rows from region 'APAC' with latency >= 102, newest first.\n\n### Schema\n```sql\nCREATE TABLE facts (fact_id BIGINT, site_id BIGINT, category_id BIGINT, event_ts TIMESTAMP, ingest_seq BIGINT, region VARCHAR(20), status VARCHAR(20), latency DECIMAL(18,2));\n```",
    "language": "sql",
    "solution": "SELECT * FROM facts\nWHERE region='APAC' AND latency >= 102\nORDER BY event_ts DESC;",
    "explanation": "### Final SQL\n```sql\nSELECT * FROM facts\nWHERE region='APAC' AND latency >= 102\nORDER BY event_ts DESC;\n```\n\n### Explanation\nFiltering is the primary pattern.",
    "tags": ["sql","sql-coding","sql-leetcode","where"]
  },
  {
    "id": "SF-ARCH-0001",
    "title": "Virtual Warehouses · A education team is designing a Snowflake workload around course events",
    "difficulty": "Hard",
    "type": "MCQ",
    "topic": "Snowflake",
    "bank": "snowflake_advanced_architect",
    "description": "### Question\nA education team is designing a Snowflake workload around course events. The primary requirement is to isolate compute workloads while sharing the same stored data. Which choice best fits the requirement?\n\nA. separate virtual warehouses for independent workloads\nB. increase retention settings even though the problem is unrelated to historical recovery\nC. rebuild all downstream tables from scratch on every run\nD. use a single always-on warehouse for every workload regardless of contention",
    "language": "text",
    "solution": "### Correct Answer\n**A**\n\nSeparate virtual warehouses for independent workloads.",
    "explanation": "The key concept is Virtual Warehouses. Separate virtual warehouses isolate compute while sharing the same stored data.",
    "tags": ["mcq","snowflake","snowflake-advanced-architect","virtual-warehouses"]
  },
  {
    "id": "ENT-0001",
    "title": "Sales & Commercial | Bookings & Orders | BI and ELT workloads contend on the same virtual warehouse",
    "difficulty": "Hard",
    "type": "enterprise_incident",
    "topic": "Snowflake",
    "bank": "enterprise_scenarios_1800",
    "description": "### Scenario\nIn a Dell-scale enterprise, the Sales & Commercial domain operates the 'Bookings & Orders' data product using Snowflake. Data arrives from Salesforce; SAP Sales Orders and is consumed by Power BI; downstream domain data products and APIs. During production, BI and ELT workloads contend on the same virtual warehouse.\n\n### Observed Symptoms\nFailed or slow jobs, conflicting row counts/KPIs, stale dashboard freshness, unexpected cost or queueing, manual extracts, and disagreement over the failure domain.\n\n### Business Impact\nRisk to forecast accuracy, bookings visibility, seller decisions, and executive pipeline reporting.\n\n### Evidence Available\nquery history/profile; warehouse/cluster metrics; queue time; credit/cost history; schedules; concurrency by workload",
    "language": "text",
    "solution": "CREATE WAREHOUSE IF NOT EXISTS SALES_COMMERCIAL_BI_WH WAREHOUSE_SIZE='MEDIUM' AUTO_SUSPEND=60 AUTO_RESUME=TRUE;\nCREATE WAREHOUSE IF NOT EXISTS SALES_COMMERCIAL_ELT_WH WAREHOUSE_SIZE='LARGE' AUTO_SUSPEND=120 AUTO_RESUME=TRUE;",
    "explanation": "Investigate workload isolation, concurrency, compute sizing, scheduling overlap, and cost controls. Validate queue time and normalized cost before and after remediation.",
    "tags": ["consumption-serving","data-engineering-scenario","sales-commercial","snowflake","warehouse-sizing-cost"]
  }
] as DemoQuestion[];

export const bankCounts = { python: 2000, sql: 3000, pyspark: 2000, snowflake: 3000, dataEngineering: 7800, cloud: 2000, ai: 3000, total: 24800 };
