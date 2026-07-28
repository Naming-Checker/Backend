# Naming Checker — Backend

HTTP API для сервиса проверки нейминга с целью помочь юристам определять схожие названия и логотипы. Каркас на **FastAPI**, слои: domain -> application -> infrastructure / presentation.

## Технологии

- Python 3.10–3.14 (локально); прод-образ и CI на **3.11**  
- FastAPI, Uvicorn  
- Pydantic / pydantic-settings  
- pytest, httpx, Ruff, mypy

## Локальный запуск

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# эквивалентно: pip install -e ".[dev]"
python src/manage.py run-server
```

Документация OpenAPI: http://127.0.0.1:8000/docs  
Интеграционные контракты: `../system_analysis/docs/api_contracts.md`  

Переменные окружения (при необходимости) — в `.env`; см. `src/naming_check_backend/shared/settings.py`.

Тесты:

```bash
make test
```

## Text similarity (TextModel + sidecar)

Исходники пайплайна (офлайн, без вызовов HF из рантайма контейнера при `local_files_only`) лежат в каталоге **`TextModel/`** в монорепе: см. [`TextModel/src/README.md`](../TextModel/src/README.md). Текущий индекс — **LaBSE** (`sentence-transformers/LaBSE`, dim 768):

- `embeddings.pt` / `embeddings.f16.npy` (+ `.meta.json`)
- `aliases.parquet`, `class_mask.npy`, `manifest.json`
- snapshot `models/LaBSE/`

Runtime similarity для тестового стенда и прокси-ручки backend — контейнер **`backend/text-model-service/`** ([`text-model-service/README.md`](text-model-service/README.md)): переменные `EMBEDDINGS_PT_PATH`, `ALIASES_PARQUET_PATH`, `CLASS_MASK_PATH`, `MODEL_PATH` внутри контейнера (`/app/models/...`).

Пример запроса к backend (нужны запущенные backend и `text-model-service`, см. переменные ниже):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/text-similarity/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"EUROPLEX","mktu_codes":[5,35],"top_k":10}'
```

## Sidecar-поиск на стенде (logo + text)

Публичные прокси-ручки backend:

- `POST /api/v1/logo-similarity/search` -> `visual-model-service`
- `GET /api/v1/logo-similarity/preview` -> `visual-model-service` (прокси выдачи preview по `logo_path`)
- `POST /api/v1/text-similarity/search` -> `text-model-service`

Полезные переменные для локальной отладки backend sidecar-вызовов (см. `src/naming_check_backend/shared/settings.py`):

```bash
VISUAL_MODEL_SERVICE_BASE_URL=http://127.0.0.1:9000
VISUAL_MODEL_SERVICE_TIMEOUT_SECONDS=300
VISUAL_MODEL_SERVICE_MAX_TOP_K=200

TEXT_MODEL_SERVICE_BASE_URL=http://127.0.0.1:9100
TEXT_MODEL_SERVICE_TIMEOUT_SECONDS=120
TEXT_MODEL_SERVICE_MAX_TOP_K=200

# CORS для локального фронта (порт `python -m http.server` и т.п.).
# По умолчанию в коде уже задан безопасный список origin’ов localhost; переменная переопределяет его полностью.
# Деплой на тестовый стенд также добавляет те же значения в `.env.runtime` (см. `deploy-test-stand.yml`).
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080
CORS_ALLOW_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS
CORS_ALLOW_HEADERS=*
CORS_ALLOW_CREDENTIALS=false
```

## CI/CD

### Merge gate

- Required GitHub check для `main`: `backend-required-checks`
- Workflow с этим check: `.github/workflows/pull-request-ci.yml`
- Чтобы реально запретить merge до завершения проверок, в GitHub нужно включить branch protection для `main` и отметить `backend-required-checks` как required status check.

### Деплой на тестовый стенд

- Workflow деплоя: `.github/workflows/deploy-test-stand.yml`
- Триггеры: **`workflow_dispatch` (ручной запуск)** и `push` в `main`
- Перед деплоем workflow повторно запускает `make ci`
- На сервер rsync’ится весь каталог backend, затем там собираются **три** образа Docker:
  - `naming-check-backend` (этот сервис)
  - `visual-model-service` (каталог `visual-model-service/`, FastAPI поверх embeddings + VGG16, CPU-only)
  - `text-model-service` (каталог `text-model-service/`, FastAPI поверх text embeddings + ruBERT snapshot, CPU-only)

Обязательные `GitHub Secrets`:

- `TEST_STAND_HOST`
- `TEST_STAND_USER`
- `TEST_STAND_SSH_KEY`

Опциональные `GitHub Secrets`:

- `TEST_STAND_PORT` (по умолчанию `22`)
- `TEST_STAND_APP_DIR` (по умолчанию `/opt/naming-check-backend`)
- `TEST_STAND_BIND_PORT` (по умолчанию `8000`, публикация порта контейнера бэкенда наружу)
- `TEST_STAND_ENV_FILE` (многострочный runtime `.env` для контейнера бэкенда; при необходимости переопределите `VISUAL_MODEL_SERVICE_BASE_URL` и `TEXT_MODEL_SERVICE_BASE_URL` — в деплое по умолчанию `http://visual-model-service:9000` и `http://text-model-service:9000` в общей Docker-сети)
- `TEST_STAND_VISUAL_MODELS_DIR` (хост-путь к папке с **`logos_embedding.pt`**, **`logos_embedding.csv`**, **`similarity.safetensors`**, **`logos_embedding_colors.csv`**, по умолчанию `/opt/visual-model-models`)
- `TEST_STAND_VISUAL_DATA_DIR` (хост-путь к корню с изображениями логотипов для preview, по умолчанию `/opt/visual-model-data`)
- `TEST_STAND_VISUAL_BIND_PORT` (порт на **localhost** сервера для визуального сервиса, по умолчанию `9000`; наружу не торчит, только `127.0.0.1`)
- `TEST_STAND_VISUAL_ENV_FILE` (доп. строки в `.env` визуального сервиса)
- `TEST_STAND_TEXT_MODELS_DIR` (хост-путь к папке с **`embeddings.f16.npy`** / **`embeddings.pt`**, **`aliases.parquet`**, **`class_mask.npy`**, **`manifest.json`** и **`LaBSE/`**, по умолчанию `/opt/text-model-models`)
- `TEST_STAND_TEXT_BIND_PORT` (порт на **localhost** сервера для текстового сервиса, по умолчанию `9100`; наружу не торчит, только `127.0.0.1`)
- `TEST_STAND_TEXT_ENV_FILE` (доп. строки в `.env` текстового сервиса, например override `MODEL_PATH`)
- `TEST_STAND_ELK_ENV_FILE` (обязательно для ELK: минимум `ELASTIC_PASSWORD=...`; см. `infra/logging/.env.elk.example`)
- `TEST_STAND_MONITORING_ENV_FILE` (опционально: `GRAFANA_ADMIN_PASSWORD`, `ALERTMANAGER_TELEGRAM_BOT_TOKEN`, `ALERTMANAGER_TELEGRAM_CHAT_ID`; см. `infra/monitoring/.env.monitoring.example`)

### Централизованное логирование (ELK)

На тестовом стенде при деплое поднимаются **Elasticsearch 8.17**, **Kibana** и **Filebeat** (`infra/logging/docker-compose.elk.yml`). Логи приложений — JSON в stdout, retention **1 день**.

- Kibana публикуется на **`http://<TEST_STAND_HOST>:5601`** (логин **`elastic`**, пароль `ELASTIC_PASSWORD`). Откройте TCP **5601** в firewall / security group облака, если UI не открывается снаружи.
- После деплоя Kibana открывает **Discover** с data view `logs-*` (все сервисы) и отдельными view по сервисам. Индексы: `logs-<service>-YYYY.MM.DD` (Filebeat). Saved searches: ошибки, 5xx, медленные запросы.
- **APM**: Kibana → Observability → APM — транзакции по каждой HTTP-ручке, span'ы вызовов backend → sidecars.
- Диагностика: `bash infra/logging/scripts/diagnose-filebeat.sh` на сервере.
- Локально: `bash scripts/start-elk-local.sh` (создаёт `infra/logging/.env.elk.local` из example).
- На уже работающем VPS без повторного bootstrap: `sudo sysctl -w vm.max_map_count=262144` и persist в `/etc/sysctl.d/99-elasticsearch.conf`.

### Мониторинг (Grafana + Prometheus)

При деплое стенда поднимается monitoring stack из `infra/monitoring/docker-compose.monitoring.yml`:

- `grafana` на `http://<TEST_STAND_HOST>:3000` (логин `admin`, пароль из `GRAFANA_ADMIN_PASSWORD` в `TEST_STAND_MONITORING_ENV_FILE`; если secret не задан, используется `admin`).
- `prometheus` на `127.0.0.1:9090` (доступ с хоста стенда, наружу не публикуется).
- **Provisioning as code**: datasource Prometheus и дашборды из `infra/monitoring/grafana/provisioning/` и `infra/monitoring/grafana/dashboards/`.
- Папка в Grafana: **Naming Check**. Home dashboard: **Overview** (`naming-check-home`).
- Дашборды:
  - **Overview** — сводка: apps UP, RPS, errors, latency, CPU/RAM, probes.
  - **Services** — HTTP-метрики приложений (RPS, p50/p95/p99, 4xx/5xx, handlers).
  - **Infrastructure** — хост и контейнеры (CPU, RAM, disk, probes, top containers).
  - **Load Testing** — анализ нагрузочных прогонов: RPS, p95/p99, error rate, CPU/RAM, сценарии S1–S4.
- Recording rules для load test: `infra/monitoring/prometheus/recording_rules.yml`
- Документация метрик: `infra/monitoring/docs/metrics_collection.md`
- Источники метрик: `node-exporter`, `cAdvisor`, blackbox health probes и **`/metrics`** на всех трёх сервисах.
- Наполнить графики тестовым трафиком: `BACKEND_URL=http://<host>:8000 REQUESTS=30 bash scripts/generate-monitoring-traffic.sh`
- Диагностика: `bash infra/monitoring/scripts/diagnose-prometheus.sh` на сервере.

### Нагрузочное тестирование

Окружение и runbook: [`docs/performance/load_test_environment.md`](docs/performance/load_test_environment.md). Цели и метрики: [`docs/performance/load_testing_goals.md`](docs/performance/load_testing_goals.md).

На test stand после деплоя:

```bash
bash scripts/load/prepare-load-test-env.sh   # или make load-test-prepare
make load-test-smoke                          # smoke (1 VU, 30s)
make load-test-baseline                       # baseline (1 VU, 10m)
make load-test-stress                         # stress (ramping-vus)
```

Универсальный запуск профиля:

```bash
PROFILE=baseline LOAD_TEST_DURATION=5m LOAD_TEST_VUS=2 bash scripts/load/run-load-test.sh
PROFILE=stress LOAD_TEST_STAGES="2m:5,4m:15,4m:30,2m:5" bash scripts/load/run-load-test.sh
```

k6 запускается в Docker (`infra/load-testing/`), цель — только test stand (allowlist хостов). Сценарии реализуют mixed поток S1–S4 (веса по умолчанию 60/25/10/5). Во время прогона смотрите Grafana → **Naming Check → Load Testing** (refresh 10 s).

Проверка метрик: `bash scripts/load/verify-metrics-collection.sh` или `make load-test-metrics`.

Отчёт после прогона: `make load-test-report PROFILE=smoke` или `bash scripts/load/export-load-test-summary.sh --report`. Шаблон: [`docs/performance/load_test_report_template.md`](docs/performance/load_test_report_template.md).

Ручной запуск из CI/CD: workflow `.github/workflows/load-test.yml` (`workflow_dispatch`, profile/duration/vus/rps).

### Алертинг (Alertmanager)

- Правила: `infra/monitoring/prometheus/alerts.yml` (service down, error rate, latency, RAM, disk).
- Alertmanager на `127.0.0.1:9093` (UI для просмотра активных алертов; с хоста стенда).
- Уведомления в **Telegram**: задайте в `TEST_STAND_MONITORING_ENV_FILE`:
  - `ALERTMANAGER_TELEGRAM_BOT_TOKEN=...`
  - `ALERTMANAGER_TELEGRAM_CHAT_ID=...`
- Тест алерта: `bash infra/monitoring/scripts/test-alert.sh` (на VPS по SSH).
- Runbook: [infra/monitoring/docs/alerting_runbook.md](infra/monitoring/docs/alerting_runbook.md).

Одноразовая подготовка сервера (Ubuntu): скрипт `scripts/bootstrap-test-stand-ubuntu.sh` (Docker, пользователь, каталоги, `vm.max_map_count`). **Пароли в Actions не использовать** — только ключ в secrets.

После загрузки кода деплоя убедитесь, что на сервер скопированы артефакты эмбеддингов (их нет в Git — `.pt` ~380MB):

```bash
sudo mkdir -p /opt/visual-model-models
sudo cp logos_embedding.pt logos_embedding.csv \
  similarity.safetensors logos_embedding_colors.csv \
  /opt/visual-model-models/
```

Из монорепы (рядом `VisualModel/`): после настройки **SSH по ключу**:

```bash
bash scripts/sync-visual-artifacts-to-test-stand.sh
```

Скопирует эмбеддинги в `/opt/visual-model-models/` и архив логотипов в `/opt/visual-model-data/data/logos/` (~ несколько GB, время зависит от канала).

Локальная проверка контейнера визуального сервиса (нужны файлы моделей):

```bash
bash scripts/smoke-visual-service-local.sh /path/to/models
```

Текстовые артефакты для `text-model-service` (их нет в Git):

```bash
sudo mkdir -p /opt/text-model-models
sudo cp embeddings.f16.npy embeddings.f16.npy.meta.json aliases.parquet class_mask.npy manifest.json /opt/text-model-models/
sudo rsync -a --exclude onnx --exclude .cache LaBSE/ /opt/text-model-models/LaBSE/
```

Из монорепы (рядом `TextModel/`): после настройки **SSH по ключу**:

```bash
TEXT_ARTIFACTS_DIR=../TextModel/models bash scripts/sync-text-artifacts-to-test-stand.sh
```

Скопирует индекс (memmap/pt + parquet + class_mask) и snapshot `LaBSE/` в `/opt/text-model-models/`.

Локальная проверка контейнера текстового сервиса:

```bash
bash scripts/smoke-text-service-local.sh /path/to/models
```

Требования к серверу стенда:

- установлен Docker;
- пользователь из `TEST_STAND_USER` может выполнять Docker-команды;
- открыт порт, на который публикуется контейнер бэкенда (`TEST_STAND_BIND_PORT`);
- визуальный сервис слушает на `127.0.0.1:$TEST_STAND_VISUAL_BIND_PORT` на том же сервере;
- текстовый сервис слушает на `127.0.0.1:$TEST_STAND_TEXT_BIND_PORT` на том же сервере;
- не использовать пароль в workflow, доступ настроить только через `SSH`-ключ в secrets.

## Участие

1. Форкните репозиторий или получите доступ к организации.  
2. Ветка от `main`, осмысленное имя (`feature/...`, `fix/...`).  
3. Коммиты с понятным сообщением.  
4. Pull request с кратким описанием изменений; убедитесь, что `make test` и линтеры проходят (`make format`, `make lint` по проекту).
