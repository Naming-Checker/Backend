# Naming Checker — Backend

HTTP API для сервиса проверки нейминга с целью помочь юристам определять схожие названия и логотипы. Каркас на **FastAPI**, слои: domain -> application -> infrastructure / presentation.

## Технологии

- Python 3.10–3.11  
- FastAPI, Uvicorn  
- Pydantic / pydantic-settings  
- pytest, httpx, Ruff, mypy

## Локальный запуск

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python src/manage.py run-server
```

Документация OpenAPI: http://127.0.0.1:8000/docs  
Интеграционные контракты: `../system_analysis/docs/api_contracts.md`  

Переменные окружения (при необходимости) — в `.env`; см. `src/naming_check_backend/shared/settings.py`.

Тесты:

```bash
make test
```

## Logo Comparison MVP (VisualModel)

В `logo_comparison` доступен MVP-режим in-process интеграции с `VisualModel`.

Включение через `.env`:

```bash
VISUALMODEL_ENABLED=true
VISUALMODEL_SIMILARITY_MODULE_PATH=../VisualModel/src/similarity.py
VISUALMODEL_EMBEDDINGS_PATH=../VisualModel/models/logos_embedding.pt
VISUALMODEL_ASSETS_ROOT=../VisualModel/data/logos
VISUALMODEL_TOP_K=10
VISUALMODEL_SCORE_THRESHOLD=0
VISUALMODEL_SOURCE=visual_model
```

Smoke-запрос:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/logo-comparison" \
  -H "Content-Type: application/json" \
  -d '{
    "reference_logo": {
      "asset_ref": "file:///absolute/path/to/query-logo.png",
      "media_type": "image/png",
      "filename": "query-logo.png"
    },
    "suspicious_logo": {
      "asset_ref": "logo://suspicious/probi-market.png",
      "media_type": "image/png",
      "filename": "probi-market.png"
    },
    "mktu_codes": [35]
  }'
```

Примечания:

- Для MVP `asset_ref` поддерживает `file://...`, `logo://...` и обычный путь.
- Если `VISUALMODEL_ENABLED=false`, endpoint работает в режиме placeholder-ответа.
- Для рабочего VisualModel-режима должны быть доступны `torch/torchvision` и файлы embeddings.

## CI/CD

### Merge gate

- Required GitHub check для `main`: `backend-required-checks`
- Workflow с этим check: `.github/workflows/pull-request-ci.yml`
- Чтобы реально запретить merge до завершения проверок, в GitHub нужно включить branch protection для `main` и отметить `backend-required-checks` как required status check.

### Деплой на тестовый стенд

- Workflow деплоя: `.github/workflows/deploy-test-stand.yml`
- Триггер: `push` в `main`
- Перед деплоем workflow повторно запускает `make ci`
- Выкладка идёт на тестовый стенд по `SSH`-ключу и собирает Docker-образ прямо на сервере

Обязательные `GitHub Secrets`:

- `TEST_STAND_HOST`
- `TEST_STAND_USER`
- `TEST_STAND_SSH_KEY`

Опциональные `GitHub Secrets`:

- `TEST_STAND_PORT` (по умолчанию `22`)
- `TEST_STAND_APP_DIR` (по умолчанию `/opt/naming-check-backend`)
- `TEST_STAND_BIND_PORT` (по умолчанию `8000`)
- `TEST_STAND_ENV_FILE` (многострочный runtime `.env` для контейнера)

Требования к серверу стенда:

- установлен Docker;
- пользователь из `TEST_STAND_USER` может выполнять Docker-команды;
- открыт порт, на который публикуется контейнер;
- не использовать пароль в workflow, доступ настроить только через `SSH`-ключ в secrets.

## Участие

1. Форкните репозиторий или получите доступ к организации.  
2. Ветка от `main`, осмысленное имя (`feature/...`, `fix/...`).  
3. Коммиты с понятным сообщением.  
4. Pull request с кратким описанием изменений; убедитесь, что `make test` и линтеры проходят (`make format`, `make lint` по проекту).
