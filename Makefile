.PHONY: prod dev test lint typecheck help _python_dev

# ── Приложение (Docker) ──────────────────────────────────────────
dev:  ## Запустить dev (localhost:17832, dev БД)
	@echo "→ http://localhost:17832"
	docker compose up --build

prod:  ## Запустить production (localhost:17833, prod БД)
	@echo "→ http://localhost:17833"
	PORT=17833 APP_ENV=production docker compose up --build

# ── Инструменты разработчика (локально, через venv) ──────────────
_python_dev:
	@[ -d .venv ] || python3 -m venv .venv
	@.venv/bin/pip install -e "backend/[dev]"

test: _python_dev  ## Запустить тесты
	.venv/bin/python -m pytest

lint: _python_dev  ## Линтинг (ruff)
	.venv/bin/ruff check .

typecheck: _python_dev  ## Проверка типов (mypy)
	.venv/bin/mypy backend/src

# ── Help ─────────────────────────────────────────────────────────
help:  ## Показать доступные команды
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  %-12s %s\n", $$1, $$2}'
