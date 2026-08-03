const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const axe = require("axe-core");

const WEB_URL = process.env.RIGOR_WEB_URL || "http://127.0.0.1:3001";
const API_URL = process.env.RIGOR_API_URL || "http://127.0.0.1:8002";
const ARTIFACT_DIR = process.env.RIGOR_E2E_ARTIFACT_DIR || "test-results/rigor-e2e";
const TERMINAL = new Set(["COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"]);

fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

function compose(args, options = {}) {
  const result = spawnSync("docker", ["compose", ...args], {
    encoding: "utf8",
    env: process.env,
    input: options.input,
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.status !== 0 && !options.allowFailure) {
    throw new Error(
      `docker compose ${args.join(" ")} failed\n${result.stdout || ""}\n${result.stderr || ""}`,
    );
  }
  return (result.stdout || "").trim();
}

function sql(statement) {
  return compose([
    "exec",
    "-T",
    "postgres",
    "psql",
    "-U",
    "rigor",
    "-d",
    "rigor",
    "-v",
    "ON_ERROR_STOP=1",
    "-Atc",
    statement,
  ]);
}

async function waitFor(predicate, { timeout = 60_000, interval = 500, label = "condition" } = {}) {
  const deadline = Date.now() + timeout;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await predicate();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw new Error(`Timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
}

async function api(page, pathname, options = {}) {
  return page.evaluate(
    async ({ apiUrl, pathname, options }) => {
      const token = window.localStorage.getItem("rigor.auth.access-token");
      const response = await fetch(`${apiUrl}${pathname}`, {
        method: options.method || "GET",
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(options.headers || {}),
        },
        ...(options.body ? { body: JSON.stringify(options.body) } : {}),
      });
      const text = await response.text();
      if (!response.ok) {
        throw new Error(`${response.status}: ${text.slice(0, 500)}`);
      }
      return text ? JSON.parse(text) : null;
    },
    { apiUrl: API_URL, pathname, options },
  );
}

async function executionId(page) {
  return page.evaluate(() => {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key || !key.startsWith("rigor.active-execution:")) continue;
      const raw = window.localStorage.getItem(key);
      if (!raw) continue;
      try {
        const parsed = JSON.parse(raw);
        if (typeof parsed.executionId === "string") return parsed.executionId;
      } catch {
        // Ignore unrelated local state.
      }
    }
    return null;
  });
}

async function waitForExecution(page, id, predicate, label, timeout = 90_000) {
  return waitFor(
    async () => {
      const view = await api(page, `/api/v1/executions/${encodeURIComponent(id)}`);
      return predicate(view) ? view : null;
    },
    { timeout, interval: 750, label },
  );
}

async function axeScan(page, name) {
  await page.addScriptTag({ content: axe.source });
  const result = await page.evaluate(async () =>
    window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      resultTypes: ["violations"],
    }),
  );
  const reportPath = path.join(ARTIFACT_DIR, `${name}-axe.json`);
  fs.writeFileSync(reportPath, JSON.stringify(result, null, 2));
  const blocking = result.violations.filter((item) =>
    ["serious", "critical"].includes(item.impact || ""),
  );
  if (blocking.length > 0) {
    const summary = blocking
      .map((item) => `${item.id} (${item.impact}): ${item.nodes.length} node(s)`)
      .join("\n");
    throw new Error(`Accessibility violations on ${name}:\n${summary}`);
  }
}

async function keyboardActivate(page, matcher) {
  for (let index = 0; index < 40; index += 1) {
    await page.keyboard.press("Tab");
    const label = await page.evaluate(() => {
      const element = document.activeElement;
      return `${element?.getAttribute?.("aria-label") || ""} ${element?.textContent || ""}`.trim();
    });
    if (matcher.test(label)) {
      await page.keyboard.press("Enter");
      return;
    }
  }
  throw new Error(`Keyboard focus never reached ${matcher}`);
}

async function completeOnboarding(page) {
  await page.goto(`${WEB_URL}/onboarding`, { waitUntil: "domcontentloaded" });
  await page.getByText(/Target roles/i).waitFor({ timeout: 30_000 });
  const role = page.getByRole("button", { name: /Senior backend engineer/i });
  if ((await role.getAttribute("class"))?.includes("selected") !== true) {
    await role.click();
  }
  await page.getByRole("button", { name: /Complete onboarding|Save profile changes/i }).click();
  await page.waitForURL((url) => url.pathname === "/", { timeout: 30_000 });
}

async function openExecutablePractice(page) {
  await page.goto(`${WEB_URL}/question-bank`, { waitUntil: "domcontentloaded" });
  await page.locator("a.question-card").first().waitFor({ timeout: 30_000 });
  const hrefs = await page.locator("a.question-card").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("href")).filter(Boolean),
  );
  for (const href of hrefs) {
    await page.goto(new URL(href, WEB_URL).toString(), { waitUntil: "domcontentloaded" });
    const start = page.getByRole("link", { name: /Start practice/i });
    if (await start.isVisible().catch(() => false)) {
      await start.click();
      await page.getByRole("button", { name: /Run public tests/i }).waitFor({ timeout: 30_000 });
      return;
    }
  }
  throw new Error("No executable hosted question was found on the first published page.");
}

function slowSource(source) {
  const lines = source.split("\n");
  const definition = lines.findIndex((line) => /^\s*def\s+\w+\s*\(/.test(line));
  if (definition < 0) return source;
  const leading = lines[definition].match(/^\s*/)?.[0] || "";
  const indent = `${leading}    `;
  lines.splice(
    definition + 1,
    0,
    `${indent}for _rigor_spin in range(300_000_000):`,
    `${indent}    pass`,
  );
  return lines.join("\n");
}

async function setEditor(page, transform) {
  const editor = page.getByLabel("Python source code");
  const current = await editor.inputValue();
  await editor.fill(transform(current));
}

async function queueFromUi(page, buttonName) {
  await page.getByRole("button", { name: buttonName }).click();
  const id = await waitFor(() => executionId(page), {
    timeout: 20_000,
    interval: 200,
    label: `${buttonName} execution id`,
  });
  return id;
}

function directSqlSmoke() {
  const program = String.raw`
import json
import urllib.request
from uuid import uuid4
execution_id = str(uuid4())
payload = {
    "schema_version": 1,
    "execution_id": execution_id,
    "attempt": 1,
    "source_code": "SELECT value FROM numbers ORDER BY value",
    "schema_sql": "CREATE TABLE numbers(value integer);",
    "seed_sql": "INSERT INTO numbers VALUES (2), (1);",
    "statement_timeout_ms": 3000,
    "tests": [{"id": "sql-restart", "visibility": "public", "input": None}],
}
request = urllib.request.Request(
    "http://sql-runner:8082/run",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    result = json.load(response)
assert result["status"] == "COMPLETED", result
assert result["tests"][0]["actual"]["rows"] == [[1], [2]], result
print(json.dumps(result, sort_keys=True))
`;
  compose(["exec", "-T", "execution-controller", "python", "-"], { input: program });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") process.stderr.write(`[browser] ${message.text()}\n`);
  });

  try {
    await page.goto(`${WEB_URL}/sign-in`, { waitUntil: "domcontentloaded" });
    await axeScan(page, "sign-in");
    await keyboardActivate(page, /Practice as a candidate/i);
    await page.waitForURL((url) => !url.pathname.includes("sign-in"), { timeout: 30_000 });
    await completeOnboarding(page);
    await axeScan(page, "onboarding-complete-home");

    await openExecutablePractice(page);
    await axeScan(page, "practice-workspace");

    const firstRun = await queueFromUi(page, /Run public tests/i);
    const firstResult = await waitForExecution(
      page,
      firstRun,
      (view) => TERMINAL.has(view.status),
      "initial execution result",
    );
    await page.getByText(/All evaluated tests passed|Review the failing cases|Execution (failed|timeout)/i).waitFor({ timeout: 30_000 });

    const attemptBeforeDuplicate = Number(
      sql(`SELECT attempt_count FROM execution_requests WHERE id='${firstRun}'::uuid`),
    );
    sql(`
      INSERT INTO local_execution_queue(body)
      SELECT payload::text FROM execution_outbox
       WHERE aggregate_type='execution'
         AND aggregate_id='${firstRun}'::uuid
         AND event_type='execution.requested';
      INSERT INTO local_execution_queue(body)
      SELECT payload::text FROM execution_outbox
       WHERE aggregate_type='execution'
         AND aggregate_id='${firstRun}'::uuid
         AND event_type='execution.requested';
    `);
    await waitFor(() => Number(sql("SELECT count(*) FROM local_execution_queue")) === 0, {
      timeout: 30_000,
      label: "duplicate delivery drain",
    });
    const attemptAfterDuplicate = Number(
      sql(`SELECT attempt_count FROM execution_requests WHERE id='${firstRun}'::uuid`),
    );
    if (attemptAfterDuplicate !== attemptBeforeDuplicate) {
      throw new Error("Duplicate queue delivery changed a terminal execution attempt.");
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    await setEditor(page, slowSource);
    const restartExecution = await queueFromUi(page, /Run public tests/i);
    await waitForExecution(
      page,
      restartExecution,
      (view) => view.status === "RUNNING",
      "execution to enter RUNNING before controller restart",
      45_000,
    );
    compose(["restart", "execution-controller"]);
    await waitFor(
      () => {
        try {
          execFileSync("curl", ["--fail", "--silent", `${API_URL}/readyz`], { stdio: "ignore" });
          return true;
        } catch {
          return false;
        }
      },
      { timeout: 45_000, label: "API readiness after controller restart" },
    );
    const recovered = await waitForExecution(
      page,
      restartExecution,
      (view) => TERMINAL.has(view.status),
      "expired lease recovery after controller restart",
      120_000,
    );
    if (recovered.attempt < 2) {
      throw new Error("Controller restart did not exercise an expired-lease retry.");
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    compose(["stop", "execution-controller"]);
    const queuedCancel = await queueFromUi(page, /Run public tests/i);
    await page.getByRole("button", { name: /Cancel execution/i }).click();
    await waitForExecution(
      page,
      queuedCancel,
      (view) => view.status === "CANCELLED",
      "queued cancellation",
    );
    compose(["start", "execution-controller"]);
    await waitForExecution(
      page,
      queuedCancel,
      (view) => view.status === "CANCELLED",
      "queued cancellation after controller recovery",
    );

    await page.reload({ waitUntil: "domcontentloaded" });
    await setEditor(page, slowSource);
    const runningCancel = await queueFromUi(page, /Run public tests/i);
    await waitForExecution(
      page,
      runningCancel,
      (view) => view.status === "RUNNING",
      "running cancellation precondition",
      45_000,
    );
    await page.getByRole("button", { name: /Cancel execution/i }).click();
    await waitForExecution(
      page,
      runningCancel,
      (view) => view.status === "CANCELLED",
      "running cancellation",
    );
    await new Promise((resolve) => setTimeout(resolve, 12_000));
    await waitForExecution(
      page,
      runningCancel,
      (view) => view.status === "CANCELLED",
      "cancelled execution to remain terminal",
    );

    await page.reload({ waitUntil: "domcontentloaded" });
    compose(["stop", "python-runner"]);
    const unavailable = await queueFromUi(page, /Run public tests/i);
    await waitForExecution(
      page,
      unavailable,
      (view) => view.status === "RUNNING" || view.attempt >= 1,
      "runner unavailable dispatch",
      45_000,
    );
    compose(["start", "python-runner"]);
    const retried = await waitForExecution(
      page,
      unavailable,
      (view) => TERMINAL.has(view.status),
      "runner recovery retry",
      120_000,
    );
    if (retried.attempt < 2) {
      throw new Error("Runner outage did not produce a durable retry.");
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    compose(["stop", "python-runner"]);
    const exhausted = await queueFromUi(page, /Run public tests/i);
    const exhaustedResult = await waitForExecution(
      page,
      exhausted,
      (view) => TERMINAL.has(view.status),
      "maximum attempt exhaustion",
      150_000,
    );
    if (exhaustedResult.status !== "FAILED" || exhaustedResult.attempt < 3) {
      throw new Error(`Expected exhausted execution failure, got ${JSON.stringify(exhaustedResult)}`);
    }
    compose(["start", "python-runner"]);

    compose(["restart", "execution-postgres"]);
    compose(["up", "-d", "--wait", "sql-runner"]);
    directSqlSmoke();

    await page.reload({ waitUntil: "domcontentloaded" });
    const submit = await queueFromUi(page, /Submit for evaluation/i);
    await waitForExecution(page, submit, (view) => TERMINAL.has(view.status), "submission result");
    await page.getByText(/DETERMINISTIC EVALUATION|Review the failing cases|Execution failed/i).waitFor({ timeout: 30_000 });

    await page.goto(`${WEB_URL}/mock-interviews`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /Start mock exam/i }).waitFor({ timeout: 30_000 });
    await axeScan(page, "mock-exam-intro");
    await keyboardActivate(page, /Start mock exam/i);
    await page.getByLabel("Question navigator").waitFor({ timeout: 15_000 });
    await axeScan(page, "mock-exam-running");

    await page.goto(`${WEB_URL}/learning-paths`, { waitUntil: "domcontentloaded" });
    await page.getByRole("navigation", { name: /Curriculum domains/i }).waitFor({ timeout: 30_000 });
    await axeScan(page, "learning-paths");

    await page.goto(`${WEB_URL}/question-bank`, { waitUntil: "domcontentloaded" });
    await page.getByRole("tab", { name: /Hosted questions/i }).focus();
    await page.keyboard.press("Enter");
    const selected = await page.getByRole("tab", { name: /Hosted questions/i }).getAttribute("aria-selected");
    if (selected !== "true") throw new Error("Keyboard activation did not select Hosted questions.");
    await axeScan(page, "question-bank");

    const evidence = {
      initial: firstResult,
      controller_restart: recovered,
      queued_cancel: queuedCancel,
      running_cancel: runningCancel,
      runner_recovery: retried,
      exhausted: exhaustedResult,
      submission: submit,
    };
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "execution-evidence.json"),
      JSON.stringify(evidence, null, 2),
    );
  } catch (error) {
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "failure.png"), fullPage: true }).catch(() => {});
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "failure.txt"),
      `${error.stack || error}\n`,
    );
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
