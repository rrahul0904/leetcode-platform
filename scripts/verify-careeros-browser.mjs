import { spawn } from "node:child_process";
import { existsSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const baseUrl = process.env.CAREEROS_BROWSER_BASE_URL ?? "http://127.0.0.1:3001";
const driverPort = 9515;
const driverUrl = `http://127.0.0.1:${driverPort}`;
const webdriverElementKey = "element-6066-11e4-a52e-4f735466cecf";
const resumePath = "/tmp/careeros-browser-resume.pdf";

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
    const message = payload.value?.message ?? `${method} ${path} returned ${response.status}`;
    throw new Error(message);
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
  const requests = [];
  Object.defineProperty(window, "__careerosBrowserRequests", {
    configurable: true,
    value: requests,
  });

  const json = (value, status = 200) =>
    new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init.method ?? (typeof input === "string" ? "GET" : input.method) ?? "GET").toUpperCase();
    const body = typeof init.body === "string" ? init.body : null;

    if (url.startsWith("/api/backend") || url.startsWith(window.location.origin + "/api/backend") || url.endsWith("/__careeros-browser-upload")) {
      requests.push({ url, method, body });
    }

    if (url.endsWith("/api/v1/auth/me")) {
      return json({
        authentication_provider: "local-oidc",
        display_name: "Browser Candidate",
        email: "browser-candidate@rigor.test",
        roles: ["candidate"],
      });
    }

    if (url.endsWith("/api/v1/profile")) {
      return json({
        target_roles: ["Backend Engineer"],
        target_companies: [],
        experience_level: "senior",
        preferred_programming_language: "python",
        weekly_study_hours: 6,
        interview_date: null,
        strong_areas: [],
        weak_areas: [],
        preparation_intensity: "focused",
      });
    }

    if (url.endsWith("/api/v1/career/jobs") && method === "GET") return json([]);
    if (url.endsWith("/livez")) return json({ status: "ok" });

    if (url.endsWith("/api/v1/files/presign-upload") && method === "POST") {
      return json({
        file_id: "file-1",
        method: "PUT",
        upload_url: window.location.origin + "/__careeros-browser-upload",
        expires_seconds: 300,
        storage_key: "candidates/browser/file-1/resume.pdf",
      });
    }

    if (url.endsWith("/__careeros-browser-upload") && method === "PUT") {
      return new Response("", { status: 200 });
    }

    if (url.endsWith("/api/v1/career/resumes/file-1/extract") && method === "POST") {
      return json({
        document_id: "document-1",
        candidate_file_id: "file-1",
        file_name: "resume.pdf",
        mime_type: "application/pdf",
        extraction_method: "pdf_text",
        character_count: 1234,
        created_at: "2026-09-17T12:00:00Z",
      });
    }

    if (url.endsWith("/api/v1/career/jobs/analyze") && method === "POST") {
      return json({
        job_title: "Backend Engineer",
        company: "Browser Test Co",
        source_url: null,
        fit_score: 82,
        skill_coverage: 86,
        language_overlap: 71,
        matched_skills: ["Python", "PostgreSQL"],
        missing_skills: ["Kubernetes"],
        resume_skills: ["Python", "PostgreSQL"],
        priority_keywords: ["backend", "python"],
        strengths: ["Your resume contains direct evidence for Python."],
        risks: ["Kubernetes is not explicit in the resume."],
        interview_questions: [
          {
            category: "experience",
            focus: "Python",
            question: "Tell me about a Python system you owned.",
            coaching_note: "Use measurable impact.",
          },
        ],
        scoring_explanation: "Explainable deterministic score.",
        job_id: "job-1",
        document_id: "document-1",
        analysis_id: "analysis-1",
        status: "saved",
        scoring_version: "deterministic-v1",
        created_at: "2026-09-17T12:00:00Z",
      });
    }

    if (url.startsWith("/api/backend") || url.startsWith(window.location.origin + "/api/backend")) {
      return json({});
    }

    return originalFetch(input, init);
  };
})();
`;

let driver;
let sessionId;
let driverOutput = "";

async function execute(script, args = []) {
  return webdriver("POST", `/session/${sessionId}/execute/sync`, { script, args });
}

async function findElement(selector) {
  const value = await webdriver("POST", `/session/${sessionId}/element`, {
    using: "css selector",
    value: selector,
  });
  const id = value?.[webdriverElementKey] ?? value?.ELEMENT;
  if (!id) throw new Error(`WebDriver did not return an element id for ${selector}`);
  return id;
}

async function sendKeys(elementId, text) {
  await webdriver("POST", `/session/${sessionId}/element/${elementId}/value`, {
    text,
    value: Array.from(text),
  });
}

try {
  await waitFor(
    "CareerOS development server",
    async () => {
      const response = await fetch(`${baseUrl}/sign-in`);
      return response.ok;
    },
    60_000,
  );

  writeFileSync(resumePath, "%PDF-1.4\nCareerOS browser smoke resume\n%%EOF\n");

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
          args: ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1200"],
        },
      },
    },
  });
  sessionId = session.sessionId;
  if (!sessionId) throw new Error("ChromeDriver did not return a session id");

  await webdriver("POST", `/session/${sessionId}/url`, { url: `${baseUrl}/sign-in` });
  await execute(
    "window.localStorage.setItem('rigor.auth.access-token', 'browser-smoke-token'); return true;",
  );
  await webdriver("POST", `/session/${sessionId}/goog/cdp/execute`, {
    cmd: "Page.addScriptToEvaluateOnNewDocument",
    params: { source: browserApiStub },
  });

  await webdriver("POST", `/session/${sessionId}/url`, { url: `${baseUrl}/career` });
  await waitFor("CareerOS workspace", () =>
    execute(
      "return location.pathname === '/career' && document.body.innerText.includes('Choose resume');",
    ),
  );

  const fileInput = await findElement("#career-resume-file");
  await sendKeys(fileInput, resumePath);
  await waitFor("resume extraction completion", () =>
    execute(
      "return document.body.innerText.includes('Resume ready') && document.body.innerText.includes('1,234 extracted characters');",
    ),
  );

  const jobDescription = await findElement("#career-job-description");
  await sendKeys(
    jobDescription,
    "Backend engineer role requiring Python, PostgreSQL, Kubernetes, reliable APIs, and system design.",
  );
  await waitFor("enabled Analyze role button", () =>
    execute("const button = document.querySelector('button[type=submit]'); return Boolean(button && !button.disabled);"),
  );

  const submitButton = await findElement("button[type=submit]");
  await webdriver("POST", `/session/${sessionId}/element/${submitButton}/click`, {});
  await waitFor("CareerOS analysis result", () =>
    execute(
      "return Boolean(document.querySelector('[aria-label=\"Fit score 82 out of 100\"]')) && document.body.innerText.includes('Explainable deterministic score.');",
    ),
  );

  const requests = await execute("return window.__careerosBrowserRequests ?? [];");
  const presign = requests.find((request) => request.url.endsWith("/api/v1/files/presign-upload"));
  const upload = requests.find((request) => request.url.endsWith("/__careeros-browser-upload"));
  const extract = requests.find((request) => request.url.endsWith("/api/v1/career/resumes/file-1/extract"));
  const analyze = requests.find((request) => request.url.endsWith("/api/v1/career/jobs/analyze"));

  if (!presign || !upload || !extract || !analyze) {
    throw new Error(`Browser flow missed an expected request: ${JSON.stringify(requests)}`);
  }
  const presignBody = JSON.parse(presign.body);
  if (presignBody.category !== "resume" || !/^[0-9a-f]{64}$/.test(presignBody.checksum_sha256)) {
    throw new Error(`Unexpected presign payload: ${presign.body}`);
  }
  if (upload.method !== "PUT") throw new Error(`Expected upload PUT, got ${upload.method}`);

  const analyzeBody = JSON.parse(analyze.body);
  if (analyzeBody.document_id !== "document-1" || "resume_text" in analyzeBody) {
    throw new Error(`Analysis did not use persisted document id: ${analyze.body}`);
  }

  console.log("CareerOS real-browser upload flow passed: hash -> presign -> PUT -> extract -> analyze by document id.");
} catch (error) {
  if (driverOutput.trim()) console.error(driverOutput.trim());
  throw error;
} finally {
  if (sessionId) {
    try {
      await webdriver("DELETE", `/session/${sessionId}`);
    } catch {
      // Preserve the primary failure if ChromeDriver has already exited.
    }
  }
  if (driver && !driver.killed) driver.kill("SIGTERM");
  if (existsSync(resumePath)) unlinkSync(resumePath);
}
