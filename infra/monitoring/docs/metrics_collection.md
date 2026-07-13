# Сбор метрик для нагрузочного тестирования

> **Задача:** [#74 — Подготовить инфраструктуру для нагрузочного тестирования](https://github.com/Naming-Checker/Backend/issues/74)  
> **Критерии:** сбор метрик приложения, БД и инфраструктуры; Grafana-дашборды для анализа  
> **Связанные документы:** [load_testing_goals.md](../../docs/performance/load_testing_goals.md), [load_test_environment.md](../../docs/performance/load_test_environment.md)

## 1. Обзор

Метрики собираются **Prometheus** (scrape каждые 15 с) и визуализируются в **Grafana**. Во время нагрузочного теста основной дашборд: **Naming Check → Load Testing**.

| Слой | Статус MVP | Источник | Дашборд |
|------|------------|----------|---------|
| Приложение (HTTP) | ✅ | `/metrics` на 3 сервисах | Load Testing, Services |
| Инфраструктура (хост) | ✅ | node-exporter | Load Testing, Infrastructure |
| Контейнеры | ✅ | cAdvisor | Load Testing, Infrastructure |
| Health probes | ✅ | blackbox-exporter | Overview |
| База данных | ⏳ N/A | postgres-exporter, clickhouse-exporter (план) | Load Testing § DB |

## 2. Метрики приложения

Экспортируются через `prometheus_client` (`shared/prometheus_metrics.py` и sidecar-копии).

| Метрика | Тип | Labels | Назначение |
|---------|-----|--------|------------|
| `http_requests_total` | Counter | `service`, `method`, `handler`, `status` | RPS, error rate |
| `http_request_duration_seconds` | Histogram | `service`, `method`, `handler`, `status` | p50/p95/p99 latency |
| `service_health_status` | Gauge | `service` | 1 = healthy, 0 = degraded |

### Scrape targets (Prometheus)

| Job | Target | Путь |
|-----|--------|------|
| `naming-check-backend` | `naming-check-backend:8000` | `/metrics` |
| `visual-model-service` | `visual-model-service:9000` | `/metrics` |
| `text-model-service` | `text-model-service:9000` | `/metrics` |

### Recording rules (агрегаты для load test)

Файл: [`prometheus/recording_rules.yml`](../prometheus/recording_rules.yml)

| Запись | Описание |
|--------|----------|
| `naming_check:load_test:http_requests:rate5m` | Суммарный RPS |
| `naming_check:load_test:http_requests_error_rate:percent5m` | Error rate % |
| `naming_check:load_test:http_request_duration_seconds:p95` | P95 latency |
| `naming_check:load_test:http_request_duration_seconds:p99` | P99 latency |
| `naming_check:scenario_rps:rate5m` | RPS по handler S1–S4 |
| `naming_check:scenario_duration_seconds:p95` | P95 по handler S1–S4 |

### Сценарии → handlers

| Сценарий | Handler |
|----------|---------|
| S1 text search | `/api/v1/text-similarity/search` |
| S2 logo search | `/api/v1/logo-similarity/search` |
| S3 preview | `/api/v1/logo-similarity/preview` |
| S4 health | `/api/v1/health` |

## 3. Метрики инфраструктуры

| Job | Метрики | Использование при load test |
|-----|---------|----------------------------|
| `node-exporter` | `node_cpu_seconds_total`, `node_memory_*`, `node_filesystem_*` | CPU/RAM/disk хоста; пороги 70/90% |
| `cadvisor` | `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` | Утилизация ML sidecars |
| `blackbox-http` | `probe_success`, `probe_duration_seconds` | Доступность сервисов |

## 4. Метрики базы данных (план)

На MVP persistence-слой не развёрнут. В `prometheus.yml` закомментированы будущие jobs:

```yaml
# - job_name: postgresql
#   static_configs:
#     - targets: ["postgres-exporter:9187"]
# - job_name: clickhouse
#   static_configs:
#     - targets: ["clickhouse-exporter:9116"]
```

После внедрения БД — раскомментировать targets и добавить панели на дашборде Load Testing.

## 5. Grafana dashboards

| Dashboard | UID | Назначение |
|-----------|-----|------------|
| **Load Testing** | `load-testing` | **Основной** для анализа нагрузочных прогонов |
| Overview | `naming-check-home` | Сводка стенда |
| Services | `services-metrics` | Детальные HTTP-метрики |
| Infrastructure | `infrastructure` | Хост и все контейнеры |

Provisioning: `grafana/provisioning/dashboards/dashboards.yml` → папка **Naming Check**.

### Load Testing dashboard

- **Refresh:** 10 s (для live-наблюдения во время теста)
- **Time range по умолчанию:** last 15 min
- **Пороги** на stat-панелях совпадают с [load_testing_goals.md](../../docs/performance/load_testing_goals.md) §4.2–4.3

## 6. Проверка сбора метрик

На test stand:

```bash
bash infra/monitoring/scripts/diagnose-prometheus.sh
bash scripts/load/verify-metrics-collection.sh
```

Ожидаемый результат `verify-metrics-collection.sh`: все проверки `[OK]`.

Если `http_requests_total NO DATA` — сгенерируйте трафик:

```bash
bash scripts/generate-monitoring-traffic.sh
# или smoke load test:
bash scripts/load/run-smoke-load-test.sh
```

## 7. Связь с критериями PASS/FAIL

| Метрика из goals doc | Prometheus / Grafana |
|----------------------|----------------------|
| RPS | `naming_check:load_test:http_requests:rate5m` |
| Latency p95/p99 | recording rules + Load Testing stat panels |
| Error rate | `naming_check:load_test:http_requests_error_rate:percent5m` |
| CPU/RAM | node-exporter + cAdvisor panels |
| DB load | N/A на MVP |

## 8. Definition of Done (#74, метрики + дашборды)

- [ ] Prometheus scrape всех app targets (`up == 1`)
- [ ] Recording rules загружены (`naming_check:load_test:*` в Explore)
- [ ] Дашборд **Load Testing** виден в Grafana
- [ ] Во время smoke/трафика панели RPS, latency, error rate обновляются
- [ ] CPU/RAM панели показывают данные хоста и контейнеров
