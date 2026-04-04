.PHONY: test lint typecheck all dev setup

setup:
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv .venv; \
	fi
	@echo "Installing dependencies..."
	@. .venv/bin/activate && pip install -e backend/ || true
	@cd frontends/web && npm install --prefer-offline > /dev/null 2>&1 || true

test: setup
	cd backend && python -m pytest

lint: setup
	ruff check .

typecheck: setup
	mypy backend/src

all: lint typecheck test

dev: setup
	@echo "Starting backend (PID will be shown)..."
	@PYTHONPATH=backend/src .venv/bin/uvicorn backend.infrastructure.api.app:app --port 8002 --reload &
	@echo "Starting frontend..."
	@cd frontends/web && npm run dev
