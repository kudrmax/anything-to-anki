# anything-to-anki

## Архитектура: Clean Architecture

Проект строго следует Clean Architecture (Uncle Bob). Три слоя в backend, фронтенды полностью отделены.

### Правило зависимостей (НАРУШЕНИЕ = БЛОКЕР)

```
frontends/* ──► application (use cases, DTOs)
                    │
                    ▼
               domain (entities, ports)
                    ▲
                    │
              infrastructure (реализует порты)
```

- **domain** не импортирует НИЧЕГО из application, infrastructure или frontends
- **application** импортирует ТОЛЬКО из domain
- **infrastructure** реализует интерфейсы из domain/ports
- **frontends** зависят от backend как от пакета, импортируют use cases и DTOs

### Слои backend

- `domain/entities/` — бизнес-сущности (dataclasses)
- `domain/value_objects/` — неизменяемые объекты-значения (frozen dataclasses, enums)
- `domain/ports/` — интерфейсы (ABC) для внешних зависимостей
- `domain/exceptions.py` — доменные исключения
- `application/use_cases/` — сценарии использования
- `application/dto/` — входные/выходные модели (pydantic)
- `infrastructure/` — реализации портов, внешние сервисы, БД
- `infrastructure/container.py` — DI-контейнер, единственное место сборки зависимостей

### Backend vs Frontend

- `backend/` и `frontends/` — полностью независимые top-level компоненты
- Backend не знает о существовании фронтендов
- Фронтенд — заменяемый presentation layer, НЕ содержит бизнес-логики
- Каждый фронтенд — отдельный пакет со своим pyproject.toml

### Порты и адаптеры

- Интерфейсы (ABC) определяются в `domain/ports/`
- Реализации — в `infrastructure/`
- Use cases получают зависимости через конструктор (constructor injection)
- Сборка зависимостей — только в `infrastructure/container.py`

## Код

- Строгая типизация: type hints везде, `mypy --strict`
- Сущности — `dataclasses` (frozen где возможно)
- DTOs — `pydantic` models
- Composition over inheritance
- Никаких plain dicts для структурированных данных
- `Any` запрещён без явного обоснования в комментарии

## Тесты

- `tests/unit/domain/` — чистый Python, без моков
- `tests/unit/application/` — моки только для портов (ABC)
- `tests/integration/` — реальные реализации infrastructure
- Маркеры pytest: `@pytest.mark.unit`, `@pytest.mark.integration`
- Запуск: `make test`

## Запрещено

- Импорт infrastructure в domain или application
- Бизнес-логика во фронтендах
- Прямое создание infrastructure-объектов в use cases (только DI)
- Plain dicts вместо dataclass/pydantic для структурированных данных
