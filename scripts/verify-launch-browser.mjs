import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const baseUrl = process.env.LAUNCH_BROWSER_BASE_URL ?? "http://localhost:3001";
const driverPort = 9516;
const driverUrl = `http://127.0.0.1:${driverPort}`;
const webdriverElementKey = "element-6066-11e4-a52e-4f735466cecf";

const launchRoutes = [
  "/question-bank",
  "/companies",
  "/design-lab",
  "/pr-review",
  "/ai-arena",
  "/mock-interviews",
  "/learning-paths",
  "/attempts",
  "/progress",
];

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitFor(label, check, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  const suffix = lastError instanceof Error ? `: ${lastError.message}` : "";
  throw new Error(`Timed out waiting for ${label}${suffix}`);
}

async function webdriver(method, path, body) {
  const response = await fetch(`${driverUrl}${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || payload.value?.error) {
    throw new Error(payload.value?.message ?? `${method} ${path} returned ${response.status}`);
  }
  return payload.value;
}

function chromeDriverCommand() {
  if (process.env.CHROMEWEBDRIVER) {
    const candidate = join(process.env.CHROMEWEBDRIVER, "chromedriver");
    if (existsSync(candidate)) return candidate;
  }
  return "chromedriver";
}

const browserApiStub = String.raw`
(() => {
  const originalFetch = window.fetch.bind(window);
  const json = (value, status = 200) =>
    new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;

    if (url.endsWith("/api/v1/auth/me")) {
      return json({
        authentication_provider: "local-oidc",
        display_name: "Launch Candidate",
        email: "launch-candidate@rigor.test",
        roles: ["candidate"],
      });
    }

    if (url.endsWith("/api/v1/profile")) {
      return json({
        target_roles: ["Senior Software Engineer"],
        target_companies: [],
        experience_level: "senior",
        preferred_programming_language: "python",
        weekly_study_hours: 8,
        interview_date: null,
        strong_areas: [],
        weak_areas: [],
        preparation_intensity: "focused",
      });
    }

    if (url.endsWith("/livez")) return json({ status: "ok" });

    if (
      url.startsWith("/api/backend") ||
      url.startsWith(window.location.origin + "/api/backend")
    ) {
      return json({ detail: "launch browser smoke stub" }, 404);
    }

    return originalFetch(input, init);
  };
})();
`;

let driver;
let sessionId;
let driverOutput = "";

async function execute(scriptSource, args = []) {
  return webdriver("POST", `/session/${sessionId}/execute/sync`, {
    script: scriptSource,
    args,
  });
}

try {
  await waitFor(
    "development server",
    async () => {
      const response = await fetch(`${baseUrl}/sign-in`);
      return response.ok;
    },
    60_000,
  );

  driver = spawn(chromeDriverCommand(), [`--port=${driverPort}`], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  driver.stdout.on("data", (chunk) => {
    driverOutput += chunk.toString();
  });
  driver.stderr.on("data", (chunk) => {
    driverOutput += chunk.toString();
  });

  await waitFor("ChromeDriver", async () => {
    const response = await fetch(`${driverUrl}/status`);
    if (!response.ok) return false;
    const status = await response.json();
    return status.value?.ready === true;
  });

  const session = await webdriver("POST", "/session", {
    capabilities: {
      alwaysMatch: {
        browserName: "chrome",
        "goog:chromeOptions": {
          args: [
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1440,1200",
          ],
        },
      },
    },
  });
  sessionId = session.sessionId;
  if (!sessionId) throw new Error("ChromeDriver did not return a session id");

  await webdriver("POST", `/session/${sessionId}/url`, {
    url: `${baseUrl}/sign-in`,
  });
  await execute(
    "window.localStorage.setItem('rigor.auth.access-token', 'launch-smoke-token'); return true;",
  );
  await webdriver("POST", `/session/${sessionId}/goog/cdp/execute`, {
    cmd: "Page.addScriptToEvaluateOnNewDocument",
    params: { source: browserApiStub },
  });

  for (const route of launchRoutes) {
    await webdriver("POST", `/session/${sessionId}/url`, {
      url: `${baseUrl}${route}`,
    });
    await waitFor(route, () =>
      execute(
        `return location.pathname === ${JSON.stringify(route)}
          && document.body.innerText.includes("SKILLSFORGE AI")
          && document.body.innerText.trim().length > 100
          && !document.querySelector("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay");`,
      ),
    );

    const path = await execute("return location.pathname;");
    if (path !== route) {
      throw new Error(`Candidate route ${route} redirected to ${path}`);
    }
    console.log(`PASS ${route}`);
  }

  console.log(
    `Launch browser smoke passed for ${launchRoutes.length} authenticated candidate routes.`,
  );
} catch (error) {
  if (driverOutput.trim()) console.error(driverOutput.trim());
  throw error;
} finally {
  if (sessionId) {
    try {
      await webdriver("DELETE", `/session/${sessionId}`);
    } catch {
      // Preserve primary failure.
    }
  }
  if (driver && !driver.killed) driver.kill("SIGTERM");
}
