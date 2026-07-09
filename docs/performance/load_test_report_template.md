# Шаблон отчёта о нагрузочном тестировании

> Используйте после каждого прогона (smoke, baseline, peak, stress, soak).  
> Метрики можно сгенерировать автоматически — см. § «Быстрый старт».

## Быстрый старт

### На сервере test stand (Prometheus на localhost)

```bash
cd /opt/naming-check-backend

# Краткая сводка в stdout
LOOKBACK=15m PROFILE=smoke bash scripts/load/export-load-test-summary.sh

# Полный черновик отчёта в файл
PROFILE=smoke GIT_SHA=$(git rev-parse --short HEAD) \
  LOOKBACK=15m \
  OUTPUT=docs/performance/reports/smoke-$(date +%Y-%m-%d).md \
  bash scripts/load/export-load-test-summary.sh --report
```

### С ноутбука (через Grafana)

```bash
GRAFANA_URL=http://<TEST_STAND_HOST>:3000 \
GRAFANA_USER=admin \
GRAFANA_PASSWORD=<пароль> \
LOOKBACK=15m PROFILE=smoke \
bash scripts/load/export-load-test-summary.sh --report \
  > docs/performance/reports/smoke-$(date +%Y-%m-%d).md
```

**Когда запускать:** сразу после окончания k6-прогона, пока в Prometheus ещё есть данные за интервал `LOOKBACK`.

---

## Шаблон (ручное заполнение)

Скопируйте блок ниже, если не используете `--report`.

---

# Отчёт о нагрузочном тестировании

## Метаданные

| Поле | Значение |
|------|----------|
| Дата | YYYY-MM-DD HH:MM |
| Окружение | test-stand / A100 target |
| Профиль | smoke / baseline / normal / peak / stress / soak |
| Git SHA | `abc1234` |
| Образ Docker (tag) | `main-abc1234` |
| Цель API | `http://<host>:8000` |
| Интервал наблюдения | Last 15m / 1h |
| Исполнитель | |

## Контекст

- **Сценарии:** S1 text / S2 logo / S3 preview / S4 health / mixed
- **Инструмент:** k6 `infra/load-testing/k6/scripts/<script>.js`
- **Параметры:** VU=__, duration=__, target RPS=__
- **Цель прогона:** _например: проверить smoke после деплоя / найти max RPS_

## Метрики

_Вставьте вывод `export-load-test-summary.sh` или заполните таблицу:_

| Метрика | Max | Avg | Last | Порог (goals) | Статус |
|---------|-----|-----|------|---------------|--------|
| RPS (total) | | | | normal 3 / peak 7 | |
| Error rate | | | | < 1% | |
| Latency p50 | | | | — | |
| Latency p95 | | | | ≤ 10s (text MVP) | |
| Latency p99 | | | | ≤ 30s (logo MVP) | |
| Host CPU | | | | < 90% | |
| Host RAM | | | | < 90% | |

### RPS по сценариям

| Handler | Max RPS |
|---------|---------|
| `/api/v1/text-similarity/search` | |
| `/api/v1/logo-similarity/search` | |
| `/api/v1/health` | |

## Выводы

- **Устойчивая ёмкость:** ___ req/s _(max RPS при error < 1% и p95 в норме)_
- **Сравнение с целями:** _ниже / на уровне / выше normal (3) и peak (7)_
- **Общий вердикт:** PASS / FAIL / INCONCLUSIVE

### Критерии PASS (из load_testing_goals.md §6)

- [ ] Error rate (5xx) < 1%
- [ ] P95 / P99 в пределах §4.2
- [ ] CPU / RAM не в критической зоне (> 90%)
- [ ] Нет OOM / restart контейнеров (для soak)

## Bottlenecks

| Наблюдение | Вероятная причина | Действие |
|------------|-------------------|----------|
| | CPU high, RPS low | ML inference на CPU sidecar |
| | RAM растёт на soak | утечка / embeddings в памяти |
| | p95 высокий только на S2 | VGG16 + upload |

## Артефакты

- [ ] Скриншот Grafana → **Load Testing** (секция «Ёмкость RPS»)
- [ ] `export-load-test-summary.sh --report` (этот файл)
- [ ] k6 JSON/summary (если `K6_OUT` настроен)
- [ ] Kibana: slow requests > 3s за период теста

## Подпись

| Роль | ФИО | Дата |
|------|-----|------|
| Исполнитель | | |
| Ревью | | |

---

## Хранение отчётов

Рекомендуемый путь в репозитории:

```
backend/docs/performance/reports/
  smoke-2026-07-09.md
  baseline-2026-07-15.md
```

Добавьте `reports/.gitkeep` или коммитьте отчёты по договорённости команды (часто — только в wiki/Confluence, не в git).

## Связанные документы

- [load_testing_goals.md](load_testing_goals.md) — цели, пороги, PASS/FAIL
- [load_test_environment.md](load_test_environment.md) — как запускать тесты
- [metrics_collection.md](../../infra/monitoring/docs/metrics_collection.md) — откуда берутся метрики
