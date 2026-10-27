/** Local-only read-only backend stub for Chrome navigation smoke tests.
 *
 * This is intentionally NOT an employer/candidate assessment integration
 * fixture: it only prevents development SSR/BFF calls from crashing when the
 * navigation test exercises client-side routes without a running backend.
 * Production and end-to-end HTTP UAT never use this stub.
 */
import { createServer } from "node:http";

const responses = new Map([
  ["/api/v1/auth/me", {
    authentication_provider: "local-oidc",
    display_name: "Launch Candidate",
    email: "launch-candidate@rigor.test",
    roles: ["candidate"],
  }],
  ["/api/v1/profile", {
    target_roles: ["Senior Software Engineer"],
    target_companies: [],
    experience_level: "senior",
    preferred_programming_language: "python",
    weekly_study_hours: 8,
    interview_date: null,
    strong_areas: [],
    weak_areas: [],
    preparation_intensity: "focused",
  }],
  ["/livez", { status: "ok" }],
]);

const port = Number(process.env.LAUNCH_STUB_PORT ?? "8765");
const server = createServer((request, response) => {
  const pathname = new URL(request.url ?? "/", "http://127.0.0.1").pathname;
  const data = responses.get(pathname);
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "no-store");
  response.writeHead(data === undefined ? 404 : 200);
  response.end(JSON.stringify(data ?? { detail: "navigation smoke stub: not implemented" }));
});
server.listen(port, "127.0.0.1");
