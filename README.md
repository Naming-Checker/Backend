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

Исходники пайплайна (офлайн, без вызовов HF из рантайма контейнера при `local_files_only`) лежат в каталоге **`TextModel/`** в монорепе: см. [`TextModel/src/README.md`](../TextModel/src/README.md) — установка зависимостей, скачивание snapshot **`cointegrated/rubert-tiny2`** в `TextModel/models/rubert-tiny2`, сборка индекса:

```bash
cd ../TextModel
python src/embedding.py \
  --csv data/temp_trademark.csv \
  --model-path models/rubert-tiny2 \
  --output-pt models/text_embedding.pt
```

На выходе: `models/text_embedding.pt` и одноимённый sidecar **`models/text_embedding.csv`** (метаданные по строкам).

Runtime similarity для тестового стенда и прокси-ручки backend — контейнер **`backend/text-model-service/`** ([`text-model-service/README.md`](text-model-service/README.md)): там же переменные `EMBEDDINGS_PT_PATH`, `EMBEDDINGS_CSV_PATH`, `MODEL_PATH` внутри контейнера (`/app/models/...`).

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
- `TEST_STAND_VISUAL_MODELS_DIR` (хост-путь к папке с **`logos_embedding.pt`** и **`logos_embedding.csv`**, по умолчанию `/opt/visual-model-models`)
- `TEST_STAND_VISUAL_DATA_DIR` (хост-путь к корню с изображениями логотипов для preview, по умолчанию `/opt/visual-model-data`)
- `TEST_STAND_VISUAL_BIND_PORT` (порт на **localhost** сервера для визуального сервиса, по умолчанию `9000`; наружу не торчит, только `127.0.0.1`)
- `TEST_STAND_VISUAL_ENV_FILE` (доп. строки в `.env` визуального сервиса)
- `TEST_STAND_TEXT_MODELS_DIR` (хост-путь к папке с **`text_embedding.pt`**, **`text_embedding.csv`** и **`rubert-tiny2/`**, по умолчанию `/opt/text-model-models`)
- `TEST_STAND_TEXT_BIND_PORT` (порт на **localhost** сервера для текстового сервиса, по умолчанию `9100`; наружу не торчит, только `127.0.0.1`)
- `TEST_STAND_TEXT_ENV_FILE` (доп. строки в `.env` текстового сервиса, например override `MODEL_PATH`)

Одноразовая подготовка сервера (Ubuntu): скрипт `scripts/bootstrap-test-stand-ubuntu.sh` (Docker, пользователь, каталоги). **Пароли в Actions не использовать** — только ключ в secrets.

После загрузки кода деплоя убедитесь, что на сервер скопированы артефакты эмбеддингов (их нет в Git — `.pt` ~380MB):

```bash
sudo mkdir -p /opt/visual-model-models
sudo cp logos_embedding.pt logos_embedding.csv /opt/visual-model-models/
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
sudo cp text_embedding.pt text_embedding.csv /opt/text-model-models/
sudo rsync -a rubert-tiny2/ /opt/text-model-models/rubert-tiny2/
```

Из монорепы (рядом `TextModel/`): после настройки **SSH по ключу**:

```bash
bash scripts/sync-text-artifacts-to-test-stand.sh
```

Скопирует `text_embedding.pt`, `text_embedding.csv` и snapshot `rubert-tiny2/` в `/opt/text-model-models/`.

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
