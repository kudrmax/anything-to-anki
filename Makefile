.PHONY: test lint typecheck all dev

test:
	cd backend && python -m pytest

lint:
	ruff check .

typecheck:
	mypy backend/src

all: lint typecheck test

dev:
	PYTHONPATH=backend/src .venv/bin/uvicorn backend.infrastructure.api.app:app --port 8080 --reload &
	cd frontends/web && npm run dev
