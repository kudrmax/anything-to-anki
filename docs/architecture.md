# Архитектура: Clean Architecture

Backend строго следует Clean Architecture (Uncle Bob): три слоя, зависимости идут **только вовнутрь**.

## Правило зависимостей (НАРУШЕНИЕ = БЛОКЕР)

```
frontends/* ──► application ──► domain ◄── infrastructure
                (use cases,       (entities,       (реализации
                 dto)              ports)           портов)
```

- **domain** — не импортирует ничего из `application`, `infrastructure` или `frontends`
- **application** — импортирует **только** из `domain`
- **infrastructure** — реализует интерфейсы (порты) из `domain/ports`
- **frontends** — зависят от backend как от пакета, импортируют use cases и DTO

## Слои backend

Полная раскладка `backend/src/backend/`:

| Путь | Что лежит |
|---|---|
| `domain/entities/` | Бизнес-сущности (`dataclass`) |
| `domain/value_objects/` | Неизменяемые объекты-значения (frozen dataclass, enum) |
| `domain/ports/` | Интерфейсы (ABC) для всех внешних зависимостей |
| `domain/services/` | Чистые доменные сервисы (без I/O) |
| `domain/exceptions.py` | Доменные исключения |
| `application/use_cases/` | Сценарии использования — оркестрация над портами |
| `application/dto/` | Входные/выходные модели (`pydantic`) |
| `infrastructure/adapters/` | Реализации портов (внешние API, AI, файлы) |
| `infrastructure/persistence/` | SQLAlchemy-модели, репозитории, Alembic |
| `infrastructure/api/` | FastAPI endpoints, тонкие обёртки над use cases |
| `infrastructure/workers.py` | arq worker (см. `docs/workers.md`) |
| `infrastructure/container.py` | **Единственное** место сборки зависимостей (DI) |

## Порты и адаптеры

- Все внешние зависимости (БД, AI, файлы, HTTP, Anki) скрыты за интерфейсами (ABC) в `domain/ports/`
- Реализации живут в `infrastructure/adapters/` или `infrastructure/persistence/`
- Use cases получают зависимости **только** через конструктор (constructor injection)
- Сборка графа зависимостей — **только** в `infrastructure/container.py`. Никаких прямых импортов `infrastructure` из use cases
- API-роуты тоже не создают use cases руками — берут готовые из DI-контейнера
