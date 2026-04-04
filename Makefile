.PHONY: test lint typecheck all

test:
	cd backend && python -m pytest

lint:
	ruff check .

typecheck:
	mypy backend/src

all: lint typecheck test
