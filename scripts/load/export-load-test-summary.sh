#!/usr/bin/env bash
# Export load-test metrics summary from Prometheus (or Grafana proxy).
#
# Usage (on test stand server):
#   bash scripts/load/export-load-test-summary.sh
#   LOOKBACK=1h bash scripts/load/export-load-test-summary.sh
#   OUTPUT=docs/performance/reports/summary.md bash scripts/load/export-load-test-summary.sh
#
# Usage (from laptop via Grafana — Prometheus is localhost-only on VPS):
#   GRAFANA_URL=http://<host>:3000 GRAFANA_USER=admin GRAFANA_PASSWORD=... \
#     LOOKBACK=15m bash scripts/load/export-load-test-summary.sh
#
# Full report draft (metadata + metrics + empty sections):
#   PROFILE=smoke GIT_SHA=$(git rev-parse --short HEAD) \
#     OUTPUT=docs/performance/reports/smoke-$(date +%Y-%m-%d).md \
#     bash scripts/load/export-load-test-summary.sh --report
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_ENV="${ROOT}/infra/load-testing/.env.load"
REPORT_MODE=0

for arg in "$@"; do
  case "${arg}" in
    --report) REPORT_MODE=1 ;;
    -h|--help)
      sed -n '2,17p' "$0"
      exit 0
      ;;
  esac
done

if [[ -f "${LOAD_ENV}" ]]; then
  # shellcheck disable=SC1090
  set -a && source "${LOAD_ENV}" && set +a
fi

LOOKBACK="${LOOKBACK:-15m}"
PROM_URL="${PROM_URL:-${PROMETHEUS_URL:-http://127.0.0.1:9090}}"
GRAFANA_URL="${GRAFANA_URL:-}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-}"
OUTPUT="${OUTPUT:-}"
PROFILE="${PROFILE:-${LOAD_TEST_PROFILE:-unknown}}"
ENVIRONMENT="${ENVIRONMENT:-test-stand}"
GIT_SHA="${GIT_SHA:-$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)}"
TARGET_URL="${LOAD_TEST_VERIFY_URL:-${LOAD_TEST_BASE_URL:-}}"

export LOOKBACK PROM_URL GRAFANA_URL GRAFANA_USER GRAFANA_PASSWORD REPORT_MODE \
  PROFILE ENVIRONMENT GIT_SHA TARGET_URL

CONTENT="$(python3 <<'PY'
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

LOOKBACK = os.environ["LOOKBACK"]
PROM_URL = os.environ["PROM_URL"].rstrip("/")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "").rstrip("/")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "")
REPORT_MODE = os.environ.get("REPORT_MODE") == "1"
PROFILE = os.environ["PROFILE"]
ENVIRONMENT = os.environ["ENVIRONMENT"]
GIT_SHA = os.environ["GIT_SHA"]
TARGET_URL = os.environ.get("TARGET_URL", "")


def prom_query(query: str) -> list[dict]:
    if GRAFANA_URL and GRAFANA_USER and GRAFANA_PASSWORD:
        base = f"{GRAFANA_URL}/api/datasources/proxy/uid/prometheus/api/v1/query"
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, GRAFANA_URL, GRAFANA_USER, GRAFANA_PASSWORD)
        opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(password_mgr))
    else:
        base = f"{PROM_URL}/api/v1/query"
        opener = urllib.request.build_opener()

    url = f"{base}?{urllib.parse.urlencode({'query': query})}"
    try:
        with opener.open(url, timeout=15) as resp:
            payload = json.load(resp)
    except urllib.error.URLError as exc:
        print(f"ERROR: Prometheus query failed: {exc}", file=sys.stderr)
        if not GRAFANA_URL:
            print(
                "Tip: Prometheus is often 127.0.0.1-only on VPS. "
                "Use GRAFANA_URL + GRAFANA_USER + GRAFANA_PASSWORD from laptop.",
                file=sys.stderr,
            )
        sys.exit(1)

    if payload.get("status") != "success":
        print(f"ERROR: {payload.get('error', payload)}", file=sys.stderr)
        sys.exit(1)
    return payload.get("data", {}).get("result", [])


def scalar(query: str, default: str = "n/a") -> str:
    results = prom_query(query)
    if not results:
        return default
    return str(results[0].get("value", ["", default])[1])


def float_val(query: str) -> float | None:
    raw = scalar(query, "")
    if raw in ("", "n/a", "none", "NaN"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def fmt_num(value: float | None, *, unit: str = "", precision: int = 2) -> str:
    if value is None:
        return "n/a"
    if unit == "%":
        return f"{value:.{precision}f}%"
    if unit == "reqps":
        return f"{value:.{precision}f} req/s"
    if unit == "s":
        return f"{value:.{precision}f} s"
    return f"{value:.{precision}f}{unit}"


def status_rps_max(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value <= 3:
        return "PASS (≤ normal 3)"
    if value <= 7:
        return "PASS (≤ peak 7)"
    return "WARN (> peak 7)"


def status_error(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 1:
        return "PASS (< 1%)"
    if value < 5:
        return "WARN (1–5%)"
    return "FAIL (≥ 5%)"


def status_latency_p95(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value <= 3:
        return "PASS (≤ 3s ops)"
    if value <= 10:
        return "PASS (≤ 10s MVP text)"
    if value <= 30:
        return "WARN (≤ 30s MVP logo)"
    return "FAIL (> 30s)"


def status_cpu(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 70:
        return "PASS (< 70%)"
    if value < 90:
        return "WARN (70–90%)"
    return "FAIL (≥ 90%)"


lb = LOOKBACK
metrics = {
    "rps_max": float_val(f"max_over_time(naming_check:load_test:http_requests:rate5m[{lb}])"),
    "rps_avg": float_val(f"avg_over_time(naming_check:load_test:http_requests:rate5m[{lb}])"),
    "rps_last": float_val("naming_check:load_test:http_requests:rate5m"),
    "err_max": float_val(f"max_over_time(naming_check:load_test:http_requests_error_rate:percent5m[{lb}])"),
    "err_avg": float_val(f"avg_over_time(naming_check:load_test:http_requests_error_rate:percent5m[{lb}])"),
    "p50": float_val(f"avg_over_time(naming_check:http_request_duration_seconds:p50[{lb}])"),
    "p95": float_val(f"max_over_time(naming_check:load_test:http_request_duration_seconds:p95[{lb}])"),
    "p99": float_val(f"max_over_time(naming_check:load_test:http_request_duration_seconds:p99[{lb}])"),
    "cpu_max": float_val(
        f'max_over_time((100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle"}}[5m]))))[{lb}:])'
    ),
    "ram_max": float_val(
        f"max_over_time((100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))[{lb}:])"
    ),
}

scenarios: list[tuple[str, float]] = []
for result in prom_query(
    f'max by (handler) (max_over_time(naming_check:scenario_rps:rate5m[{lb}]))'
):
    handler = result.get("metric", {}).get("handler", "?")
    val = float(result.get("value", ["", "0"])[1])
    scenarios.append((handler, val))
scenarios.sort(key=lambda x: x[1], reverse=True)

now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
source = GRAFANA_URL if GRAFANA_URL else PROM_URL
lines: list[str] = []

if REPORT_MODE:
    lines.extend(
        [
            "# Отчёт о нагрузочном тестировании",
            "",
            "> Черновик: метрики заполнены автоматически. Дополните контекст, выводы и bottlenecks.",
            "",
            "## Метаданные",
            "",
            "| Поле | Значение |",
            "|------|----------|",
            f"| Дата | {now} |",
            f"| Окружение | {ENVIRONMENT} |",
            f"| Профиль | {PROFILE} |",
            f"| Git SHA | `{GIT_SHA}` |",
            f"| Цель API | {TARGET_URL or 'n/a'} |",
            f"| Интервал метрик | `{LOOKBACK}` |",
            f"| Источник | {source} |",
            "",
            "## Контекст",
            "",
            "- **Сценарии:** _заполнить (S1–S4, smoke, …)_",
            "- **Инструмент:** k6",
            "- **Цель прогона:** _заполнить_",
            "",
            "## Метрики (авто)",
            "",
        ]
    )
else:
    lines.extend(
        [
            f"# Load test summary — {now}",
            "",
            f"- Environment: **{ENVIRONMENT}**",
            f"- Profile: **{PROFILE}**",
            f"- Git SHA: `{GIT_SHA}`",
            f"- Lookback: `{LOOKBACK}`",
            f"- Source: {source}",
            "",
        ]
    )

lines.extend(
    [
        "| Метрика | Max | Avg | Last | Порог (goals) | Статус |",
        "|---------|-----|-----|------|---------------|--------|",
        f"| RPS (total) | {fmt_num(metrics['rps_max'], unit='reqps')} "
        f"| {fmt_num(metrics['rps_avg'], unit='reqps')} "
        f"| {fmt_num(metrics['rps_last'], unit='reqps')} "
        f"| normal 3 / peak 7 | {status_rps_max(metrics['rps_max'])} |",
        f"| Error rate | {fmt_num(metrics['err_max'], unit='%')} "
        f"| {fmt_num(metrics['err_avg'], unit='%')} "
        f"| — | < 1% | {status_error(metrics['err_max'])} |",
        f"| Latency p50 | — | {fmt_num(metrics['p50'], unit='s')} "
        f"| — | — | — |",
        f"| Latency p95 | {fmt_num(metrics['p95'], unit='s')} "
        f"| — | — | ≤ 10s (text MVP) | {status_latency_p95(metrics['p95'])} |",
        f"| Latency p99 | {fmt_num(metrics['p99'], unit='s')} "
        f"| — | — | ≤ 30s (logo MVP) | {status_latency_p95(metrics['p99'])} |",
        f"| Host CPU | {fmt_num(metrics['cpu_max'], unit='%')} "
        f"| — | — | < 90% | {status_cpu(metrics['cpu_max'])} |",
        f"| Host RAM | {fmt_num(metrics['ram_max'], unit='%')} "
        f"| — | — | < 90% | {status_cpu(metrics['ram_max'])} |",
        "",
    ]
)

if scenarios:
    lines.extend(["## RPS по сценариям (max за период)", "", "| Handler | Max RPS |", "|---------|---------|"])
    for handler, val in scenarios:
        lines.append(f"| `{handler}` | {fmt_num(val, unit='reqps')} |")
    lines.append("")
else:
    lines.extend(["## RPS по сценариям", "", "_Нет данных (запустите трафик и подождите ~30 с)_", ""])

if REPORT_MODE:
    lines.extend(
        [
            "## Выводы",
            "",
            "- **Устойчивая ёмкость:** _не определена / ___ req/s_",
            "- **Общий вердикт:** _PASS / FAIL / INCONCLUSIVE_",
            "",
            "## Bottlenecks",
            "",
            "- _Grafana → Load Testing; Kibana → slow requests (> 3s)_",
            "",
            "## Артефакты",
            "",
            "- [ ] Скриншот Grafana → Load Testing",
            "- [ ] k6 output (если сохраняли)",
            "",
            "## Подпись",
            "",
            "| Роль | ФИО | Дата |",
            "|------|-----|------|",
            "| Исполнитель | | |",
            "| Ревью | | |",
            "",
        ]
    )
else:
    lines.extend(
        [
            "## Verdict (auto)",
            "",
            f"- RPS max: {status_rps_max(metrics['rps_max'])}",
            f"- Error rate max: {status_error(metrics['err_max'])}",
            f"- Latency p95 max: {status_latency_p95(metrics['p95'])}",
            "",
            "Полный отчёт: `bash scripts/load/export-load-test-summary.sh --report`",
            "",
        ]
    )

print("\n".join(lines))
PY
)"

if [[ -n "${OUTPUT}" ]]; then
  mkdir -p "$(dirname "${OUTPUT}")"
  printf '%s\n' "${CONTENT}" > "${OUTPUT}"
  echo "Wrote ${OUTPUT}"
else
  printf '%s\n' "${CONTENT}"
fi
