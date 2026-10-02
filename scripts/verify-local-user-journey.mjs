import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const baseUrl = process.env.LOCAL_UAT_BASE_URL ?? "http://localhost:3001";
const driverPort = 9517;
const driverUrl = `http://127.0.0.1:${driverPort}`;
const elementKey = "element-6066-11e4-a52e-4f735466cecf";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(label, check, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(300);
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

let driver;
let sessionId;
let driverOutput = "";

async function execute(source) {
  return webdriver("POST", `/session/${sessionId}/execute/sync`, {
    script: source,
    args: [],
  });
}

async function findByXpath(xpath) {
  const value = await webdriver("POST", `/session/${sessionId}/element`, {
    using: "xpath",
    value: xpath,
  });
  const id = value[elementKey];
  if (!id) throw new Error(`Element not found for XPath: ${xpath}`);
  return id;
}

async function clickXpath(xpath) {
  const id = await findByXpath(xpath);
  await webdriver("POST", `/session/${sessionId}/element/${id}/click`);
}

async function path() {
  return execute("return location.pathname;");
}

async function bodyText() {
  return execute("return document.body.innerText;");
}

try {
  await waitFor("local web", async () => {
    const response = await fetch(`${baseUrl}/sign-in`);
    return response.ok;
  }, 60_000);

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
  await waitFor("candidate sign-in button", async () =>
    (await bodyText()).includes("Practice as a candidate"),
  );
  await clickXpath("//button[contains(., 'Practice as a candidate')]");

  await waitFor("local OIDC candidate return", async () => {
    const current = await path();
    return current === "/workspace" || current === "/onboarding";
  }, 60_000);

  if ((await path()) === "/onboarding") {
    await waitFor("onboarding form", async () =>
      (await bodyText()).includes("Turn a target interview into a focused preparation plan"),
    );
    await clickXpath("//button[contains(., 'Data architect')]");
    await clickXpath("//button[@type='submit' and contains(., 'Complete onboarding')]");
    await waitFor("workspace after onboarding", async () => (await path()) === "/workspace");
  }

  const workspaceText = await bodyText();
  if (!workspaceText.includes("SKILLSFORGE AI")) {
    throw new Error("Authenticated workspace did not render SkillForge navigation.");
  }
  console.log("PASS local OIDC sign-in + onboarding/workspace");

  await webdriver("POST", `/session/${sessionId}/url`, {
    url: `${baseUrl}/question-bank`,
  });
  await waitFor("real question bank", async () => {
    const text = await bodyText();
    return (
      (await path()) === "/question-bank"
      && text.includes("Know exactly what you can practice here")
      && text.includes("runnable")
    );
  });
  console.log("PASS real question bank");

  await webdriver("POST", `/session/${sessionId}/url`, {
    url: `${baseUrl}/progress`,
  });
  await waitFor("progress workspace", async () => {
    const text = await bodyText();
    return (await path()) === "/progress" && text.includes("SKILLSFORGE AI");
  });
  console.log("PASS persisted authenticated progress route");

  console.log("Local full-stack candidate UAT passed.");
} catch (error) {
  if (driverOutput.trim()) console.error(driverOutput.trim());
  throw error;
} finally {
  if (sessionId) {
    try {
      await webdriver("DELETE", `/session/${sessionId}`);
    } catch {
      // Preserve the primary failure.
    }
  }
  if (driver && !driver.killed) driver.kill("SIGTERM");
}
