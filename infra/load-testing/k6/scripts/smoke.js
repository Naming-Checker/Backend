import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = (__ENV.LOAD_TEST_BASE_URL || "http://naming-check-backend:8000").replace(
  /\/$/,
  "",
);

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 1,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<60000"],
    checks: ["rate>0.95"],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/api/v1/health`);
  check(health, {
    "S4 health status 200": (r) => r.status === 200,
    "S4 health body ok": (r) => r.json("status") === "ok",
  });

  const text = http.post(
    `${BASE_URL}/api/v1/text-similarity/search`,
    JSON.stringify({
      query: "EUROPLEX",
      mktu_codes: [35, 42],
      top_k: 5,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "120s" },
  );
  check(text, {
    "S1 text search status 200": (r) => r.status === 200,
    "S1 text search has matches": (r) => Array.isArray(r.json("matches")),
  });

  sleep(1);
}

export function handleSummary(data) {
  const failRate = data.metrics.http_req_failed?.values?.rate ?? 0;
  const checksRate = data.metrics.checks?.values?.rate ?? 1;
  const passed = failRate <= 0.05 && checksRate >= 0.95;
  return {
    stdout: [
      "",
      passed ? "Smoke load test: PASS" : "Smoke load test: FAIL",
      `  target: ${BASE_URL}`,
      `  http_req_failed: ${data.metrics.http_req_failed?.values?.rate ?? "n/a"}`,
      `  p95: ${data.metrics.http_req_duration?.values?.["p(95)"] ?? "n/a"} ms`,
      "",
    ].join("\n"),
  };
}
