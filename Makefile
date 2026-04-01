SERVICE_DIR := src
APP_DIR := $(SERVICE_DIR)/naming_check_backend
TESTS_DIR := $(SERVICE_DIR)/tests
VENV_BIN := .venv/bin
PYTHON := $(VENV_BIN)/python
TXT_BOLD := \e[1m
TXT_MAGENTA := \e[35m
TXT_RESET := \e[0m

.PHONY: start stop migrations docker-migrations-up docker-migrations-down \
	docker-migrations-create isort black format ruff_format ruff_lint \
	flake8 mypy lint test test-ci ruff-ci mypy-ci docker-test \
	docker-auto_test check

start:
	docker-compose up --build -d

stop:
	docker-compose stop

# Migrations

migrations:
	@if [ -f "$(SERVICE_DIR)/alembic.ini" ]; then \
		cd $(SERVICE_DIR) && export PYTHONPATH=. && $(PYTHON) -m alembic upgrade head; \
	else \
		printf "${TXT_BOLD}${TXT_MAGENTA}Alembic is not configured in this scaffold yet.${TXT_RESET}\n"; \
	fi

docker-migrations-up:
	@docker-compose run --rm app alembic upgrade $(rev)

docker-migrations-down:
	@docker-compose run --rm app alembic downgrade $(rev)

docker-migrations-create:
	@docker-compose run --rm app alembic revision --autogenerate -m "$(msg)"

# Formatting
isort:
	$(PYTHON) -m ruff check --select I --fix $(or $(arg1), $(SERVICE_DIR))

black:
	$(PYTHON) -m ruff format $(or $(arg1), $(SERVICE_DIR))

format: ruff_format ruff_lint

ruff_format:
	$(PYTHON) -m ruff format $(SERVICE_DIR)

ruff_lint:
	$(PYTHON) -m ruff check --fix --show-fixes --exit-non-zero-on-fix $(SERVICE_DIR)

# Linting
flake8:
	$(PYTHON) -m ruff check $(SERVICE_DIR)

mypy:
	$(PYTHON) -m mypy

lint:
	@printf "${TXT_BOLD}${TXT_MAGENTA}========================== RUFF FORMAT ============================${TXT_RESET}\n"
	@$(PYTHON) -m ruff format $(SERVICE_DIR)
	@printf "${TXT_BOLD}${TXT_MAGENTA}=========================== RUFF LINT =============================${TXT_RESET}\n"
	@$(PYTHON) -m ruff check --fix --show-fixes --exit-non-zero-on-fix $(SERVICE_DIR)
	@printf "${TXT_BOLD}${TXT_MAGENTA}============================ MYPY ================================${TXT_RESET}\n"
	@$(PYTHON) -m mypy

test:
	set -a && \
	if [ -f .env ]; then . ./.env; fi && \
	set +a && \
	export PYTHONPATH=$(SERVICE_DIR) && \
	$(PYTHON) -m pytest $(or $(target), $(TESTS_DIR))

test-ci:
	@printf "${TXT_BOLD}${TXT_MAGENTA}============================ TEST ================================${TXT_RESET}\n"
	@$(PYTHON) -m pytest --color=yes -ra $(TESTS_DIR)
	@printf "${TXT_BOLD}${TXT_MAGENTA}========================== END TEST ==============================${TXT_RESET}\n"

ruff-ci:
	@printf "${TXT_BOLD}${TXT_MAGENTA}============================ RUFF ================================${TXT_RESET}\n"
	@$(PYTHON) -m ruff check $(SERVICE_DIR)
	@printf "${TXT_BOLD}${TXT_MAGENTA}========================== END RUFF ==============================${TXT_RESET}\n"

mypy-ci:
	@printf "${TXT_BOLD}${TXT_MAGENTA}============================ MYPY ================================${TXT_RESET}\n"
	@$(PYTHON) -m mypy --config-file pyproject.toml
	@printf "${TXT_BOLD}${TXT_MAGENTA}========================== END MYPY ==============================${TXT_RESET}\n"

docker-test:
	@docker-compose run --rm app pytest $(or $(target), tests) -p no:warnings -vv

docker-auto_test:
	@docker-compose up -d app && docker exec -it backend_app pytest tests/autotests -p no:warnings -v

check: format lint test
