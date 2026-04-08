# Generation Pipeline Rework — ARQ + Per-Entity Status Tables

**Date:** 2026-04-07
**Status:** Draft (pending user review)

## Goal

Переработать пайплайн фоновой генерации (media + meaning) на двух уровнях:

1. **Хранение**: вынести meaning и media из "божественной" таблицы `candidates` в отдельные 1:1 таблицы `candidate_meanings` и `candidate_media`, со своими статусами и текстом ошибок.
2. **Исполнение**: заменить in-process `asyncio.create_task()` на полноценную очередь ARQ + Redis + отдельный worker-контейнер. Получить crash recovery, параллелизм, автоматические retry transient-ошибок и точечные per-candidate статусы в UI.

## Motivation

Текущая система:
- `RunMediaExtractionJobUseCase` обрабатывает 89 кандидатов последовательно за ~45с, без параллелизма.
- Если процесс падает в середине джобы — она застревает в `RUNNING` навсегда.
- Ошибки молча проглатываются (`except Exception: logger.exception(...)`), статус `FAILED` определён, но **никогда не выставляется**. В одном из недавних прогонов джоба завершилась `processed=89 failed=0`, но часть медиа на диске реально отсутствует — silent failure без следов.
- Per-candidate статусы вычисляются на фронте через `runningJob.candidate_ids → Set lookup` — это бизнес-логика на фронте, противоречит Clean Architecture проекта.
- Таблица `candidates` смешивает 4 ответственности: идентичность слова, статус ревью, AI-meaning и media.

## Non-Goals

- Замена SQLite на другую БД
- Горизонтальное масштабирование (несколько worker-нод)
- Web-dashboard для очереди ARQ (хватит логов)
- Backfill уже сгенерированных медиа в новую структуру (миграция переносит существующие данные as-is)
- Расследование конкретного silent-failure бага в этой спеке — после фазы 1 переходим в режим reproduction с новой инфраструктурой видимости

## Phasing

Работа делится на **две независимые фазы**, каждая с отдельным планом и merge-точкой.

### Phase 1 — Refactor: extract enrichment tables

**Goal:** структура хранения чище, поведение системы не меняется.

После фазы 1 приложение работает **точно так же** как сейчас (те же джобы, тот же UI, тот же in-process исполнитель), просто данные лежат в правильных местах. Это позволяет верифицировать рефакторинг изолированно от изменения исполнения.

### Phase 2 — Pipeline: ARQ + Redis + per-candidate statuses

**Goal:** новый исполнитель, видимые статусы, отмена и retry.

Опирается на структуру из фазы 1. Меняет _способ_ запуска и обновления, но не _что_ хранится.

---

# Phase 1 — DB Refactor

## Data Model

### Новые таблицы

```sql
-- 1:1 с candidates, удаляется CASCADE
CREATE TABLE candidate_meanings (
    candidate_id   INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    meaning        TEXT,            -- nullable: пока не сгенерировано
    ipa            TEXT,            -- nullable
    status         TEXT NOT NULL,   -- enum EnrichmentStatus: 'queued'|'running'|'done'|'failed'
    error          TEXT,            -- nullable: текст последней ошибки
    generated_at   TIMESTAMP        -- nullable: когда успешно сгенерировано
);

-- 1:1 с candidates, удаляется CASCADE
CREATE TABLE candidate_media (
    candidate_id     INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    screenshot_path  TEXT,
    audio_path       TEXT,
    start_ms         INTEGER,
    end_ms           INTEGER,
    status           TEXT NOT NULL,
    error            TEXT,
    generated_at     TIMESTAMP
);
```

### Удаляемые колонки из `candidates`

После миграции данных из `candidates` удаляются:
- `meaning`
- `ipa`
- `screenshot_path`
- `audio_path`
- `media_start_ms`
- `media_end_ms`

Остаются: `id`, `word`, `context`, `source_id`, `status` (LEARN/PENDING/KNOWN/SKIP), `created_at`.

### EnrichmentStatus

```python
# domain/value_objects/enrichment_status.py
class EnrichmentStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
```

В фазе 1 у всех существующих записей с заполненным meaning ставится `status = DONE`. У записей без meaning — записи в `candidate_meanings` нет вовсе (отсутствие записи = "никогда не пытались"). Симметрично для media.

## Domain Layer

### Новые value objects

```python
# domain/entities/candidate_meaning.py
@dataclass
class CandidateMeaning:
    candidate_id: int
    meaning: str | None
    ipa: str | None
    status: EnrichmentStatus
    error: str | None
    generated_at: datetime | None

# domain/entities/candidate_media.py
@dataclass
class CandidateMedia:
    candidate_id: int
    screenshot_path: str | None
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    status: EnrichmentStatus
    error: str | None
    generated_at: datetime | None
```

### Изменения `StoredCandidate`

```python
@dataclass
class StoredCandidate:
    id: int
    source_id: int
    word: str
    context: str
    status: CandidateStatus  # LEARN/PENDING/KNOWN/SKIP
    created_at: datetime
    meaning: CandidateMeaning | None  # None = ни разу не пытались
    media: CandidateMedia | None      # None = ни разу не пытались
```

Доступ через `candidate.meaning.meaning`, `candidate.media.screenshot_path` и т.д.

### Новые порты

```python
# domain/ports/candidate_meaning_repository.py
class CandidateMeaningRepository(ABC):
    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaning | None: ...

    @abstractmethod
    def upsert(self, meaning: CandidateMeaning) -> None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMeaning]: ...

# domain/ports/candidate_media_repository.py
class CandidateMediaRepository(ABC):
    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None: ...

    @abstractmethod
    def upsert(self, media: CandidateMedia) -> None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]: ...
```

`CandidateRepository` теряет методы `update_meaning_and_ipa`, `update_media_paths`, `update_media_timecodes`, `clear_media_path` — они уезжают в новые репозитории.

## Application Layer

### Обновляемые use cases (только адаптация к новой модели)

| Use case | Что меняется |
|---|---|
| `GenerateMeaningUseCase` | Пишет в `candidate_meanings` через новый репозиторий, ставит `status=DONE` |
| `RunGenerationJobUseCase` (meaning batch) | Аналогично |
| `RunMediaExtractionJobUseCase` | Пишет в `candidate_media`, ставит `status=DONE` (FAILED пока всё ещё не используется — это фаза 2) |
| `RegenerateCandidateMediaUseCase` | Аналогично + перезапись timecodes в `candidate_media` |
| `StartMediaExtractionUseCase` | Фильтр eligible по `candidate_media is None or status != DONE` |
| `StartGenerationUseCase` (meaning) | Фильтр по `candidate_meanings is None or meaning is None` |
| `CleanupMediaUseCase` | Удаляет файлы + записи в `candidate_media` (или обнуляет paths) |
| `GetMediaStorageStatsUseCase` | Читает из `candidate_media` |
| `SyncToAnkiUseCase` | Читает поля через `candidate.meaning.meaning`, `candidate.media.screenshot_path` |
| `DeleteSourceUseCase` | CASCADE удалит автоматически (через FK) |

### DTOs

```python
class CandidateMeaningDTO(BaseModel):
    meaning: str | None
    ipa: str | None
    status: Literal["queued", "running", "done", "failed"]
    error: str | None
    generated_at: datetime | None

class CandidateMediaDTO(BaseModel):
    screenshot_path: str | None  # backend возвращает абсолютный, фронт делает /media/{...}
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    status: Literal["queued", "running", "done", "failed"]
    error: str | None
    generated_at: datetime | None

class CandidateDTO(BaseModel):
    id: int
    word: str
    context: str
    status: str
    meaning: CandidateMeaningDTO | None
    media: CandidateMediaDTO | None
```

## Infrastructure Layer

### SQLAlchemy модели

`CandidateMeaningModel` и `CandidateMediaModel` с `relationship` к `CandidateModel` через `back_populates`. Cascade delete через FK + ORM.

### Alembic migration

```python
def upgrade():
    # 1. Создать candidate_meanings
    op.create_table('candidate_meanings', ...)
    op.create_table('candidate_media', ...)

    # 2. Перенести данные
    conn = op.get_bind()
    conn.execute(text("""
        INSERT INTO candidate_meanings (candidate_id, meaning, ipa, status, generated_at)
        SELECT id, meaning, ipa, 'done', created_at
        FROM candidates
        WHERE meaning IS NOT NULL
    """))
    conn.execute(text("""
        INSERT INTO candidate_media (
            candidate_id, screenshot_path, audio_path, start_ms, end_ms, status, generated_at
        )
        SELECT id, screenshot_path, audio_path, media_start_ms, media_end_ms, 'done', created_at
        FROM candidates
        WHERE screenshot_path IS NOT NULL OR audio_path IS NOT NULL
    """))

    # 3. Удалить старые колонки
    with op.batch_alter_table('candidates') as batch:
        batch.drop_column('meaning')
        batch.drop_column('ipa')
        batch.drop_column('screenshot_path')
        batch.drop_column('audio_path')
        batch.drop_column('media_start_ms')
        batch.drop_column('media_end_ms')

def downgrade():
    # обратная миграция: вернуть колонки, перенести данные обратно, удалить таблицы
```

SQLite требует `batch_alter_table` для drop column.

### Container

Регистрируются два новых репозитория, инжектятся в use cases вместо старых методов `CandidateRepository`.

## Frontend Changes (Phase 1)

**Минимальные — только адаптация к изменившейся форме DTO. UI-поведение и логика статусов в фазе 1 НЕ меняются.**

- `types.ts`: тип `Candidate` теперь содержит `meaning?: { meaning, ipa, status, error }` и `media?: { screenshot_path, audio_path, status, error, ... }` вместо плоских полей
- `CandidateCardV2.tsx`: чтения вида `candidate.meaning` → `candidate.meaning?.meaning`, `candidate.screenshot_path` → `candidate.media?.screenshot_path` и т.д.
- Существующая логика "queued/running/done" на фронте, выводимая из `runningJob.candidate_ids`, **остаётся как есть** — потому что в фазе 1 in-process джоб-таблицы (`media_extraction_jobs`, `generation_jobs`) ещё работают, и старые `/generation/status` endpoints живы.
- Никакая логика расчёта статусов в фазе 1 не вводится и не убирается. Это всё происходит в фазе 2 (см. ниже).

## Testing (Phase 1)

- Новые unit-тесты для `CandidateMeaningRepository`, `CandidateMediaRepository` (in-memory SQLite)
- Все существующие unit-тесты use cases обновляются под новые порты (моки `CandidateMeaningRepository`/`CandidateMediaRepository` вместо `CandidateRepository.update_meaning_and_ipa`)
- Integration-тест миграции: создать БД старой схемы с данными, прогнать `upgrade()`, проверить что данные перенеслись
- Smoke-тест: `make test` зелёный, ручной прогон ReviewPage и InboxPage

## Phase 1 Deliverables

- [ ] Новые таблицы и Alembic-миграция
- [ ] Domain entities + ports
- [ ] SQLA models + repositories
- [ ] Все use cases адаптированы
- [ ] DTOs обновлены
- [ ] Frontend types и компоненты адаптированы
- [ ] Все тесты зелёные
- [ ] Ручная проверка: meaning generation работает, media generation работает, cleanup работает, Anki-sync работает

---

# Phase 2 — ARQ Pipeline + Statuses + UI

## Goal

Заменить in-process исполнение на ARQ + Redis. Использовать `status`/`error` колонки из фазы 1 как источник правды для UI. Добавить глобальные кнопки cancel и retry.

## Infrastructure Changes

### docker-compose.yml

```yaml
services:
  app:
    # ... как было
    depends_on:
      - redis

  worker:
    build:
      context: .
    command: arq backend.infrastructure.workers.WorkerSettings
    environment:
      APP_ENV: ${APP_ENV:-development}
      REDIS_URL: redis://redis:6379
      AI_PROXY_URL: ${AI_PROXY_URL:-http://host.docker.internal:8766}
    volumes:
      - ./data:/data
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - ./data/redis:/data
```

Один shared volume `./data` между app и worker — оба ходят в одну SQLite БД и в один media-каталог.

### Зависимости

```toml
# backend/pyproject.toml
arq = "^0.26"
redis = "^5.0"  # ARQ зависит, но фиксируем явно
```

### WorkerSettings

```python
# backend/src/backend/infrastructure/workers.py
from arq.connections import RedisSettings

async def startup(ctx):
    ctx['session_factory'] = create_session_factory()
    ctx['container'] = Container(ctx['session_factory'])

async def shutdown(ctx):
    pass

class WorkerSettings:
    functions = [
        extract_media_for_candidate,
        generate_meanings_batch,
    ]
    redis_settings = RedisSettings.from_dsn(os.environ['REDIS_URL'])
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1         # без параллелизма: задачи строго последовательно
    job_timeout = 600    # 10 минут на задачу
```

## Job Functions

### Media (per-candidate)

```python
async def extract_media_for_candidate(ctx, candidate_id: int) -> None:
    container: Container = ctx['container']
    with container.session_scope() as session:
        use_case = container.run_media_extraction_use_case(session)
        try:
            use_case.execute_one(candidate_id)
        except PermanentMediaError as e:
            # битый видеофайл, fragment не в SRT — повтор не поможет
            container.candidate_media_repo(session).mark_failed(candidate_id, str(e))
            session.commit()
            return  # ARQ считает задачу успешной
        # transient ошибки (subprocess timeout, OSError) — пробрасываем, ARQ ретраит
```

`max_tries=2`, `backoff=5s` — настраивается через декоратор задачи или WorkerSettings.

### Meaning (per-batch)

```python
async def generate_meanings_batch(ctx, candidate_ids: list[int]) -> None:
    container: Container = ctx['container']
    with container.session_scope() as session:
        use_case = container.run_generation_job_use_case(session)
        try:
            use_case.execute_batch(candidate_ids)
        except PermanentAIError as e:
            container.candidate_meaning_repo(session).mark_batch_failed(candidate_ids, str(e))
            session.commit()
            return
        # transient (503, timeout) → raise → ретрай
```

`max_tries=3` для meaning. Пакетная единица — 15 кандидатов как сейчас.

## Status Lifecycle

| Событие | Кто пишет | `candidate_meanings/media.status` |
|---|---|---|
| API получил запрос на генерацию | Producer (FastAPI) | `QUEUED` |
| Worker подхватил задачу, attempt 1 | Worker (use case) | `RUNNING` |
| Attempt 1 raised → ARQ ждёт backoff → attempt 2 | _не пишем_ | остаётся `RUNNING` |
| Permanent error поймана внутри use case | Use case | `FAILED` + текст ошибки |
| Все retries исчерпаны | `on_job_end` hook | `FAILED` + текст последнего exception |
| Успех | Use case | `DONE` + `generated_at = now()` |

**Между ретраями статус не флиппает** — пользователь видит "Генерируется" непрерывно, без миганий.

## Permanent vs Transient Errors

```python
# Permanent — повтор не поможет
class PermanentMediaError(Exception): pass
class InvalidTimecodesError(PermanentMediaError): pass
class BadVideoFormatError(PermanentMediaError): pass
class FragmentNotInSrtError(PermanentMediaError): pass

class PermanentAIError(Exception): pass
class InvalidPromptError(PermanentAIError): pass

# Всё остальное (subprocess.TimeoutExpired, OSError, ConnectionError, etc) — transient
```

## API Changes

### Producer endpoints

```
POST   /sources/{id}/media/generate          → 202, enqueues N задач, ставит status=QUEUED
POST   /sources/{id}/media/cancel            → 200, soft cancel: убирает QUEUED-задачи из Redis, в-полёте доедают
POST   /sources/{id}/media/retry-failed      → 202, собирает FAILED → ставит в очередь как новые

POST   /sources/{id}/meanings/generate       → 202, разбивает по 15, enqueue
POST   /sources/{id}/meanings/cancel         → 200
POST   /sources/{id}/meanings/retry-failed   → 202
```

Старые `POST /generation/start`, `POST /generation/{id}/stop`, `GET /generation/status`, `POST /sources/{id}/media-extraction` **удаляются**.

### Status — derived from candidates

`GET /sources/{id}/candidates` теперь возвращает каждого кандидата с `meaning.status` и `media.status`. Фронт читает их напрямую, без отдельного `/generation/status` endpoint и без вычислений на фронте.

Опционально: `GET /sources/{id}/queue-summary` → `{queued: 12, running: 2, failed: 3, done: 72}` для шапки страницы. Это **derived view**, серверный SQL-агрегат по таблицам — никакой бизнес-логики на фронте.

## Frontend Changes (Phase 2)

### Никакой бизнес-логики

Фронт **не вычисляет** статусы. Он только отображает то, что приходит из API.

```tsx
// CandidateCardV2.tsx — meaning section
{candidate.meaning?.status === 'queued' && <Badge>В очереди</Badge>}
{candidate.meaning?.status === 'running' && <Badge>Генерируется</Badge>}
{candidate.meaning?.status === 'failed' && (
  <Badge variant="error" tooltip={candidate.meaning.error}>Ошибка</Badge>
)}
{candidate.meaning?.status === 'done' && <span>{candidate.meaning.meaning}</span>}

// аналогично для candidate.media
```

### Глобальные кнопки в шапке ReviewPage

```
[ Generate Meanings ] [ Generate Media ] [ Cancel queue ] [ Retry failed ]
```

Cancel/Retry показываются только когда есть что отменять/ретраить (queue summary).

### Polling

Заменяется на polling того же `GET /sources/{id}/candidates` — он уже содержит все статусы. Альтернатива в будущем — SSE/WebSocket, но сейчас опрос раз в 2-5 секунд при наличии in-flight задач достаточно.

## Migration of Existing Jobs Tables

Таблицы `media_extraction_jobs` и `generation_jobs` **удаляются** в фазе 2. Никакой миграции данных — это были транзиентные записи, актуальные только для in-process исполнителя.

## Local Development

`make dev` теперь поднимает 3 контейнера: `app`, `worker`, `redis`. Хот-релоад для воркера — через restart контейнера (или `arq --watch`).

## Testing (Phase 2)

- Unit-тесты use cases работают как и раньше (use case не знает о ARQ, его инжектят через worker)
- Тесты worker-функций через `arq.testing` или `fakeredis`
- Integration-тест полного цикла: enqueue → worker подхватывает → DB обновлена
- Тест отмены: enqueue 5 задач → cancel → проверить что в DB только 1 (которая в полёте) дошла до DONE/FAILED, остальные осталиcь QUEUED → удалены
- Тест retry-failed: имитировать FAILED → нажать retry → проверить что задачи снова в QUEUED

## Phase 2 Deliverables

- [ ] Redis + worker контейнеры в docker-compose
- [ ] WorkerSettings + job functions
- [ ] Permanent vs transient exception классы
- [ ] Producer endpoints (generate / cancel / retry-failed) для media и meaning
- [ ] `on_job_end` hook для финальной записи FAILED
- [ ] CandidateDTO возвращает meaning.status и media.status
- [ ] Удаление старых таблиц `media_extraction_jobs`, `generation_jobs`
- [ ] Удаление старого endpoint `/generation/*`
- [ ] Frontend: убрана вся логика вычисления статусов
- [ ] Глобальные кнопки cancel / retry в шапке
- [ ] Bug investigation: после полного перехода — повторить сценарий который давал silent failure, посмотреть на новые статусы и error-поля, починить найденную причину

---

# Open Questions / Risks

1. **Silent failure bug** (отложен): после фазы 1 пользователь повторяет сценарий, ищем repro. После фазы 2 он будет автоматически виден через `media.status = FAILED` + `media.error`.
2. **SQLite + два процесса (app + worker)**: SQLite поддерживает многопроцессную запись через WAL mode, но конкурентность ограничена. При `max_jobs=1` (без параллелизма воркера) реально пишет в БД только один процесс одновременно с API — этого должно хватить. Если будут блокировки — включаем WAL mode явно.
