# Phase 2 — Database & API Design

## Context

Phase 1 реализован: текст → список кандидатов с контекстными фрагментами. Работает через CLI, всё in-memory. Phase 2 добавляет персистентность (SQLite) и HTTP API (FastAPI), чтобы можно было сохранять источники, размечать кандидаты и вести whitelist известных слов.

## Key Decisions

| Решение | Выбор | Обоснование |
|---------|-------|-------------|
| Пользователи | Нет | Локальное приложение, один пользователь |
| Настройки | Таблица `settings` (key-value) | Персистентно, единообразно с остальными данными |
| БД | SQLite | Локальное приложение, zero config |
| Миграции | `create_all()` при старте | Alembic позже, когда схема стабилизируется |
| Async обработка | `asyncio.create_task()` + транзакции | При падении — транзакция откатывается, ничего не теряется |
| Known words | Пара (lemma, pos) | "run" NOUN и "run" VERB — разные записи |
| Phrasal verbs | Отложены (см. improvements.md) | Требует расширения пайплайна Phase 1 |
| AnkiCard | Не в Phase 2 | Отдельная фаза |
| Связь с Phase 1 | Обёртка (composition) | Пайплайн анализа остаётся чистым, новый use case оборачивает его |

## Architecture

### Размещение в слоях

```
backend/src/backend/
  domain/                          ← кольцо 1 (не меняется)
    entities/                      ← Source, StoredCandidate, KnownWord (новые)
    ports/                         ← SourceRepository, CandidateRepository и др. (новые ABC)
    value_objects/                  ← без изменений
    services/                      ← без изменений
    exceptions.py                  ← новые исключения

  application/                     ← кольцо 2
    dto/                           ← новые DTO для API
    use_cases/                     ← новые use cases (не трогаем существующий)

  infrastructure/                  ← кольцо 3
    adapters/                      ← без изменений (spacy, cefrpy, wordfreq, regex)
    persistence/                   ← NEW: SQLAlchemy models, repository implementations
    api/                           ← NEW: FastAPI handlers (routes)
    container.py                   ← расширяется

frontends/
  cli/                             ← без изменений
```

### Dependency Rule

- `domain/` не импортирует ничего из application, infrastructure, frontends
- `application/` импортирует только из domain
- `infrastructure/persistence/` реализует порты из `domain/ports/`
- `infrastructure/api/` вызывает use cases из `application/`
- Пайплайн Phase 1 (`AnalyzeTextUseCase`) остаётся без изменений

## Domain Layer (New)

### Entities

**Source** — загруженный текст:
```
id: int (autoincrement)
raw_text: str
cleaned_text: str | None (заполняется после обработки)
status: SourceStatus (new → processing → done → error)
error_message: str | None
created_at: datetime
```

**StoredCandidate** — кандидат, привязанный к источнику:
```
id: int (autoincrement)
source_id: int (FK → Source)
lemma: str
pos: str
cefr_level: str (A1..C2, UNKNOWN)
zipf_frequency: float
is_sweet_spot: bool
context_fragment: str
fragment_purity: str (clean | dirty)
occurrences: int
status: CandidateStatus (pending → learn | known | skip)
```

**KnownWord** — whitelist:
```
id: int (autoincrement)
lemma: str
pos: str
created_at: datetime
unique constraint: (lemma, pos)
```

**Setting** — настройки:
```
key: str (PK)
value: str
```

### Value Objects

**SourceStatus** — enum: `NEW`, `PROCESSING`, `DONE`, `ERROR`

**CandidateStatus** — enum: `PENDING`, `LEARN`, `KNOWN`, `SKIP`

### Ports (New ABCs)

```python
class SourceRepository(ABC):
    def create(source: Source) -> Source
    def get_by_id(source_id: int) -> Source | None
    def list_all() -> list[Source]
    def update_status(source_id: int, status: SourceStatus, ...) -> None

class CandidateRepository(ABC):
    def create_batch(candidates: list[StoredCandidate]) -> None
    def get_by_source(source_id: int) -> list[StoredCandidate]
    def get_by_id(candidate_id: int) -> StoredCandidate | None
    def update_status(candidate_id: int, status: CandidateStatus) -> None

class KnownWordRepository(ABC):
    def add(lemma: str, pos: str) -> KnownWord
    def remove(known_word_id: int) -> None
    def list_all() -> list[KnownWord]
    def exists(lemma: str, pos: str) -> bool
    def get_all_pairs() -> set[tuple[str, str]]

class SettingsRepository(ABC):
    def get(key: str, default: str | None = None) -> str | None
    def set(key: str, value: str) -> None
```

### Exceptions (New)

- `SourceNotFoundError(source_id)`
- `CandidateNotFoundError(candidate_id)`
- `KnownWordNotFoundError(known_word_id)`
- `SourceAlreadyProcessedError(source_id)`
- `InvalidCandidateStatusError(status)`

## Application Layer (New)

### Use Cases

**CreateSourceUseCase** — сохранить текст:
- Input: `raw_text: str`
- Сохраняет Source со статусом `NEW`
- Output: Source с id

**ProcessSourceUseCase** — обработать источник (async):
- Input: `source_id: int`
- Проверяет статус (должен быть `NEW` или `ERROR`)
- Ставит статус `PROCESSING`
- Вызывает `AnalyzeTextUseCase.execute()` с текстом и CEFR-уровнем из настроек
- Фильтрует результат по known words (убирает уже известные lemma+pos)
- В одной транзакции: сохраняет кандидатов + `cleaned_text` + статус `DONE`
- При ошибке: статус `ERROR` + `error_message`

**MarkCandidateUseCase** — разметить кандидата:
- Input: `candidate_id: int, status: CandidateStatus`
- Обновляет статус кандидата
- Если `KNOWN` → добавляет (lemma, pos) в KnownWord (если ещё нет)

**GetSourcesUseCase** — список источников (id, статус, дата, превью текста)

**GetSourceDetailUseCase** — детали источника + его кандидаты

**GetCandidatesUseCase** — кандидаты по source_id

**ManageKnownWordsUseCase** — list / delete из whitelist

**GetSettingsUseCase / UpdateSettingsUseCase** — чтение / обновление настроек

### DTOs (New)

```python
# Requests
class CreateSourceRequest(BaseModel):
    raw_text: str

class ProcessSourceRequest(BaseModel):
    source_id: int

class MarkCandidateRequest(BaseModel):
    status: str  # learn | known | skip

class UpdateSettingsRequest(BaseModel):
    cefr_level: str

# Responses
class SourceDTO(BaseModel):
    id: int
    raw_text_preview: str  # первые 100 символов
    status: str
    created_at: datetime
    candidate_count: int | None

class SourceDetailDTO(BaseModel):
    id: int
    raw_text: str
    cleaned_text: str | None
    status: str
    error_message: str | None
    created_at: datetime
    candidates: list[StoredCandidateDTO]

class StoredCandidateDTO(BaseModel):
    id: int
    lemma: str
    pos: str
    cefr_level: str
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    fragment_purity: str
    occurrences: int
    status: str

class KnownWordDTO(BaseModel):
    id: int
    lemma: str
    pos: str
    created_at: datetime

class SettingsDTO(BaseModel):
    cefr_level: str
```

## Infrastructure Layer (New)

### Persistence (`infrastructure/persistence/`)

**`database.py`** — engine, session factory:
- `create_engine("sqlite:///vocabminer.db")`
- `SessionLocal` — sessionmaker
- `create_tables()` — `Base.metadata.create_all()`
- `reset_stuck_processing()` — при старте сбросить зависшие `PROCESSING` → `NEW`

**`models.py`** — SQLAlchemy declarative models:
- `SourceModel`, `StoredCandidateModel`, `KnownWordModel`, `SettingModel`
- Маппинг на доменные entities через classmethods `to_entity()` / `from_entity()`

**`source_repository.py`** — реализация `SourceRepository`
**`candidate_repository.py`** — реализация `CandidateRepository`
**`known_word_repository.py`** — реализация `KnownWordRepository`
**`settings_repository.py`** — реализация `SettingsRepository`

Все репозитории получают `Session` через конструктор.

### API (`infrastructure/api/`)

**`app.py`** — FastAPI application:
- `lifespan`: create tables, reset stuck processing, init default settings (cefr_level=B1)
- CORS middleware (для будущего веб-фронтенда)

**`dependencies.py`** — FastAPI Depends:
- `get_db_session()` — yield Session с автоматическим close
- `get_container()` — DI container с session
- Factory-функции для каждого use case

**`routes/sources.py`**:
```
POST   /sources                → CreateSourceUseCase
GET    /sources                → GetSourcesUseCase
GET    /sources/{id}           → GetSourceDetailUseCase
POST   /sources/{id}/process   → ProcessSourceUseCase (async, 202)
GET    /sources/{id}/candidates → GetCandidatesUseCase
```

**`routes/candidates.py`**:
```
PATCH  /candidates/{id}       → MarkCandidateUseCase
```

**`routes/known_words.py`**:
```
GET    /known-words            → ManageKnownWordsUseCase.list
DELETE /known-words/{id}       → ManageKnownWordsUseCase.delete
```

**`routes/settings.py`**:
```
GET    /settings               → GetSettingsUseCase
PATCH  /settings               → UpdateSettingsUseCase
```

### Container (Extended)

`container.py` расширяется:
- Принимает `Session` (или session factory)
- Создаёт repository instances
- Предоставляет factory methods для всех use cases
- Существующие адаптеры (spacy, cefrpy, wordfreq, regex) — без изменений

## Async Processing Flow

```
POST /sources/{id}/process
  → handler проверяет source существует и статус NEW/ERROR
  → handler ставит статус PROCESSING (sync, сразу в БД)
  → handler запускает asyncio.create_task(_process_background(source_id))
  → handler возвращает 202 Accepted

_process_background(source_id):
  → новая DB session
  → читает source, settings
  → spaCy синхронный → запуск через asyncio.to_thread() чтобы не блокировать event loop
  → вызывает AnalyzeTextUseCase.execute(raw_text, cefr_level)
  → фильтрует по known_words
  → BEGIN TRANSACTION:
      сохраняет кандидатов
      обновляет source (cleaned_text, status=DONE)
    COMMIT
  → при ошибке: status=ERROR, error_message=str(e)

GET /sources/{id}
  → клиент поллит статус пока не DONE/ERROR
```

## Dependencies (New)

Добавить в `backend/pyproject.toml`:
```toml
"fastapi>=0.115",
"uvicorn[standard]>=0.30",
"sqlalchemy>=2.0",
```

## Testing Strategy

**Unit tests** (`tests/unit/application/`):
- Все новые use cases с моками репозиториев
- `@pytest.mark.unit`

**Integration tests** (`tests/integration/`):
- SQLAlchemy repository tests с реальной in-memory SQLite (`sqlite:///:memory:`)
- API endpoint tests через `TestClient` (FastAPI)
- `@pytest.mark.integration`

## Verification

```bash
# 1. make all (lint + typecheck + tests)
make all

# 2. Запуск сервера
cd backend && uvicorn backend.infrastructure.api.app:app --reload

# 3. Swagger UI
open http://localhost:8000/docs

# 4. Smoke test
# Создать источник → обработать → посмотреть кандидатов → разметить слово
```
