# Backend Scaffold

Шаблон HTTP API на **FastAPI** с `src`-layout и разделением на слои `domain -> application -> infrastructure / presentation`.

## Технологии

- Python 3.10–3.11  
- FastAPI, Uvicorn  
- Pydantic / pydantic-settings  
- pytest, pytest-cov, httpx, Ruff, mypy

## Локальный запуск

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python src/manage.py run-server
```

Документация OpenAPI: http://127.0.0.1:8000/docs  

Переменные окружения (при необходимости) — в `.env`; см. `src/naming_check_backend/shared/settings.py`.

## Проверки качества

```bash
make format
make lint
make test
```

## Участие

1. Форкните репозиторий или получите доступ к организации.  
2. Ветка от `main`, осмысленное имя (`feature/...`, `fix/...`).  
3. Коммиты с понятным сообщением.  
4. Pull request с кратким описанием изменений; перед отправкой убедитесь, что форматирование, линтер, type-check и тесты проходят локально.
