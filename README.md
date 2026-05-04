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

## CI/CD

### Merge gate

- Required GitHub check для `main`: `backend-required-checks`
- Workflow с этим check: `.github/workflows/pull-request-ci.yml`
- Чтобы реально запретить merge до завершения проверок, в GitHub нужно включить branch protection для `main` и отметить `backend-required-checks` как required status check.

### Деплой на тестовый стенд

- Workflow деплоя: `.github/workflows/deploy-test-stand.yml`
- Триггеры: **`workflow_dispatch` (ручной запуск)** и `push` в `main`
- Перед деплоем workflow повторно запускает `make ci`
- На сервер rsync’ится весь каталог backend, затем там собираются **два** образа Docker:
  - `naming-check-backend` (этот сервис)
  - `visual-model-service` (каталог `visual-model-service/`, FastAPI поверх embeddings + VGG16, CPU-only)

Обязательные `GitHub Secrets`:

- `TEST_STAND_HOST`
- `TEST_STAND_USER`
- `TEST_STAND_SSH_KEY`

Опциональные `GitHub Secrets`:

- `TEST_STAND_PORT` (по умолчанию `22`)
- `TEST_STAND_APP_DIR` (по умолчанию `/opt/naming-check-backend`)
- `TEST_STAND_BIND_PORT` (по умолчанию `8000`, публикация порта контейнера бэкенда наружу)
- `TEST_STAND_ENV_FILE` (многострочный runtime `.env` для контейнера бэкенда; при необходимости переопределите `VISUAL_MODEL_SERVICE_BASE_URL` — в деплое по умолчанию `http://visual-model-service:9000` в общей Docker-сети)
- `TEST_STAND_VISUAL_MODELS_DIR` (хост-путь к папке с **`logos_embedding.pt`** и **`logos_embedding.csv`**, по умолчанию `/opt/visual-model-models`)
- `TEST_STAND_VISUAL_BIND_PORT` (порт на **localhost** сервера для визуального сервиса, по умолчанию `9000`; наружу не торчит, только `127.0.0.1`)
- `TEST_STAND_VISUAL_ENV_FILE` (доп. строки в `.env` визуального сервиса)

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

Требования к серверу стенда:

- установлен Docker;
- пользователь из `TEST_STAND_USER` может выполнять Docker-команды;
- открыт порт, на который публикуется контейнер бэкенда (`TEST_STAND_BIND_PORT`);
- визуальный сервис слушает на `127.0.0.1:$TEST_STAND_VISUAL_BIND_PORT` на том же сервере;
- не использовать пароль в workflow, доступ настроить только через `SSH`-ключ в secrets.

## Участие

1. Форкните репозиторий или получите доступ к организации.  
2. Ветка от `main`, осмысленное имя (`feature/...`, `fix/...`).  
3. Коммиты с понятным сообщением.  
4. Pull request с кратким описанием изменений; убедитесь, что `make test` и линтеры проходят (`make format`, `make lint` по проекту).
