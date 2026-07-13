export function buildSummary({ profileName, baseUrl }) {
  return (data) => {
    const failRate = data.metrics.http_req_failed?.values?.rate ?? 0;
    const checksRate = data.metrics.checks?.values?.rate ?? 0;
    const p95 = data.metrics.http_req_duration?.values?.["p(95)"] ?? "n/a";

    const passed = failRate <= 0.05 && checksRate >= 0.9;

    return {
      stdout: [
        "",
        `${profileName} load test: ${passed ? "PASS" : "FAIL"}`,
        `  target: ${baseUrl}`,
        `  http_req_failed: ${failRate}`,
        `  checks: ${checksRate}`,
        `  p95: ${p95} ms`,
        "",
      ].join("\n"),
    };
  };
}
