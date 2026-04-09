# Тесты

Тесты живут в `backend/tests/`, разделены на unit и integration по слоям Clean Architecture.

## Структура

```
backend/tests/
├── unit/
│   ├── domain/            # Чистый Python, без моков, без I/O
│   ├── application/       # Use cases, моки только для портов (ABC)
│   └── infrastructure/    # Unit-тесты адаптеров там где возможно
└── integration/           # Реальные реализации: API, БД, spaCy, парсеры, pipeline
```

## Правила

- **`unit/domain`** — никаких моков вообще. Если тест требует мока — значит, в `domain` протекла зависимость, её надо убрать через порт
- **`unit/application`** — моки разрешены **только для портов** (`domain/ports/*`). Реальные сущности, реальные DTO
- **`integration/`** — реальные адаптеры: реальный SQLAlchemy (SQLite in-memory или временный файл), реальный spaCy, реальный FastAPI через `TestClient`. Никаких моков на этом уровне, кроме внешних сервисов (AI, AnkiConnect)
- Каждый тест помечается маркером `@pytest.mark.unit` или `@pytest.mark.integration` — настроено в `pyproject.toml` (`--strict-markers`)

## Запуск

```bash
make test                                        # Весь набор
cd backend && .venv/bin/pytest -m unit           # Только unit
cd backend && .venv/bin/pytest -m integration    # Только integration
cd backend && .venv/bin/pytest tests/unit/domain # Конкретный слой
```

## Асинхронщина

`pytest-asyncio` настроен в `asyncio_mode = "auto"`, отдельных декораторов не нужно.
