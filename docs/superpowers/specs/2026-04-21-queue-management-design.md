# Queue Management Page — Design Spec

## Цель

Отдельный экран для полного контроля и понимания состояния всех очередей обработки. Пользователь видит что происходит, что упало и почему, и может управлять каждой очередью.

## Что это НЕ включает

- Статистика/аналитика (отдельная задача в TASKS.md)
- Изменение приоритетов/переупорядочивание очереди

---

## UI-структура

Один экран, один роут `/queue`. Четыре зоны сверху вниз:

### 1. Шапка: фильтр + глобальные действия

- **Фильтр по источнику** — dropdown, по умолчанию «All sources». При выборе источника все три зоны ниже скоупятся на него: счётчики, список очереди, ошибки — только по этому источнику.
- **Retry All Failed** — retry всех failed-задач (или только failed в рамках выбранного источника).
- **Cancel All Queued** — cancel всех queued-задач (или только queued в рамках выбранного источника).

### 2. Блоки по типам job'ов

Пять горизонтальных блоков, по одному на каждый тип:

| Тип | Что делает | Гранулярность |
|-----|-----------|---------------|
| YouTube DL | Загрузка видео с YouTube через yt-dlp | per-source |
| Processing | Обработка источника (cleaning → analysis → timecodes) | per-source |
| Meanings | AI-генерация значений кандидатов | per-candidate (батчи по 15) |
| Media | Извлечение скриншота + аудио из видео | per-candidate |
| Pronunciation | Скачивание произношения с Cambridge | per-candidate |

Каждый блок показывает:
- Название типа
- Счётчики: `N queued` / `N running` / `N failed`
- Кнопки **Retry** (если есть failed) и **Cancel** (если есть queued) — действуют на этот тип в рамках текущего фильтра

Блоки без активности (все счётчики = 0) скрываются.

### 3. Список очереди (Queue Order)

Плоский FIFO-список всех job'ов из Redis-очереди `arq:queue`. Разделён на две подсекции:

**Running** — job'ы, выполняющиеся прямо сейчас:
- Каждый: тип (цветной badge) + название источника + кнопка Cancel
- Для Processing: дополнительно показывать текущий substage (`analyzing text`, `mapping timecodes`)

**Queued** — job'ы в очереди, пронумерованные по позиции (1, 2, 3...):
- Каждый: позиция + тип (цветной badge) + название источника + кнопка Cancel
- При большом количестве — «... ещё N jobs» с возможностью развернуть

**Фильтр по источнику** скоупит этот список: показываются только job'ы выбранного источника.

### 4. Failed-секция

Группировка: **тип job'а → тип ошибки**.

Для каждого типа job'а (Meanings, Pronunciation, YouTube DL и т.д.):
- Заголовок: `Meanings — 5 failed`
- Внутри — строки по типам ошибок:
  - Текст ошибки + количество + список источников в скобках + кнопка `retry N`
  - Пример: `AI timeout — 3 · Breaking Bad (2), TED Talk (1) · [retry 3]`

**Фильтр по источнику** скоупит: показываются только ошибки по выбранному источнику, breakdown по источникам скрывается (один источник).

---

## Пустые состояния

- Очередь полностью пуста (все счётчики = 0, нет failed) → «Очередь пуста»
- Отфильтрован источник без активности → «У этого источника нет активности в очереди»

---

## Backend

### Новые endpoints

**`GET /api/queue/global-summary`**

Агрегированная сводка по всем типам job'ов. Опциональный query-параметр `source_id` для фильтрации.

```python
class JobTypeSummary(BaseModel):
    queued: int
    running: int
    failed: int

class QueueGlobalSummary(BaseModel):
    youtube_dl: JobTypeSummary
    processing: JobTypeSummary
    meanings: JobTypeSummary
    media: JobTypeSummary
    pronunciation: JobTypeSummary
```

Для meanings/media/pronunciation — считаем по enrichment-статусам в БД (как текущий `/sources/{id}/queue-summary`, но агрегируем по всем источникам).

Для youtube_dl — job `download_youtube_video` проходит через arq. Queued/running определяется из Redis (`active_jobs:youtube_dl:{source_id}`). Failed — sources с `content_type == YOUTUBE` и `status == ERROR` (ошибка загрузки сохраняется в `source.error_message`).

Для processing — считаем sources со `status == PROCESSING` (running), `status == ERROR` (failed). Processing не имеет состояния «queued» (запускается немедленно), поэтому `queued` для этого типа всегда 0.

**`GET /api/queue/order`**

Упорядоченный список job'ов из Redis ZSET `arq:queue` + текущие running.

```python
class QueueJob(BaseModel):
    job_id: str
    job_type: str  # "meanings" | "media" | "pronunciation" | "youtube_dl"
    source_id: int
    source_title: str
    status: str  # "running" | "queued"
    position: int | None  # порядковый номер для queued, None для running
    substage: str | None  # только для processing: "cleaning_source", "analyzing_text", etc.

class QueueOrderResponse(BaseModel):
    running: list[QueueJob]
    queued: list[QueueJob]
    total_queued: int
```

Опциональный query-параметр `source_id` для фильтрации. Опциональный `limit` (по умолчанию 50) для queued-списка — frontend показывает «ещё N jobs».

**`GET /api/queue/failed`**

Ошибки, сгруппированные по типу job'а и тексту ошибки.

```python
class FailedGroup(BaseModel):
    error_text: str
    count: int
    sources: list[FailedGroupSource]  # [{source_id, source_title, count}]
    candidate_ids: list[int]  # для retry

class FailedByJobType(BaseModel):
    job_type: str
    total_failed: int
    groups: list[FailedGroup]

class QueueFailedResponse(BaseModel):
    types: list[FailedByJobType]
```

Опциональный query-параметр `source_id`.

### Новые actions

**`POST /api/queue/retry`**

```python
class RetryRequest(BaseModel):
    job_type: str  # "meanings" | "media" | "pronunciation" | "youtube_dl" | "processing"
    source_id: int | None  # None = все источники
    error_text: str | None  # None = все ошибки, иначе — только с этим текстом
```

Для per-error-type retry: передаём `error_text`, backend находит все failed candidates с таким error для данного job_type (и source_id если указан), делает retry.

**`POST /api/queue/cancel`**

```python
class CancelRequest(BaseModel):
    job_type: str  # "meanings" | "media" | "pronunciation" | "youtube_dl" | "processing"
    source_id: int | None  # None = все источники
    job_id: str | None  # None = все queued данного типа, иначе — конкретный job
```

Для per-job cancel из списка очереди: передаём `job_id`. Для cancel по типу: передаём `job_type` + опционально `source_id`.

### Архитектурные слои

**Domain ports** (`domain/ports/`):

- `QueueInspectorPort` (ABC) — абстракция для инспекции очереди задач:
  - `get_queued_jobs(source_id: int | None, limit: int) -> list[QueuedJobInfo]` — упорядоченный список job'ов в очереди
  - `get_running_jobs(source_id: int | None) -> list[QueuedJobInfo]` — текущие running job'ы
  - `cancel_job(job_id: str) -> None` — отмена конкретного job'а
  - `cancel_jobs_by_type(job_type: str, source_id: int | None) -> int` — отмена всех queued по типу
  - `get_total_queued() -> int`

  `QueuedJobInfo` — frozen dataclass в domain: `job_id`, `job_type`, `source_id`, `position`, `scheduled_at`.

- Расширение существующих репозиториев (`CandidateMeaningRepositoryPort`, `CandidateMediaRepositoryPort`, `CandidatePronunciationRepositoryPort`):
  - `count_by_status_global(status: EnrichmentStatus, source_id: int | None) -> int` — глобальный счётчик по статусу
  - `get_failed_grouped_by_error(source_id: int | None) -> list[FailedErrorGroup]` — группировка failed по тексту ошибки с breakdown по источникам
  - `get_candidate_ids_by_error(error_text: str, source_id: int | None) -> list[int]` — для retry по типу ошибки

  `FailedErrorGroup` — frozen dataclass в domain: `error_text`, `count`, `source_counts: list[SourceErrorCount]`.

**Infrastructure adapters** (`infrastructure/`):

- `ArqQueueInspector` (реализует `QueueInspectorPort`) — читает `arq:queue` ZSET, `active_jobs:*` sets, парсит job_id для извлечения типа и source_id.
- Расширение существующих SQLA-репозиториев: добавить методы `count_by_status_global`, `get_failed_grouped_by_error`, `get_candidate_ids_by_error` — SQL GROUP BY на уровне адаптера.

**Application DTOs** (`application/dto/`):

- `QueueGlobalSummaryDTO` (pydantic) — response для `/api/queue/global-summary`
- `QueueOrderDTO` (pydantic) — response для `/api/queue/order`
- `QueueFailedDTO` (pydantic) — response для `/api/queue/failed`
- `RetryRequestDTO`, `CancelRequestDTO` (pydantic) — request bodies

**Application use cases** (`application/use_cases/`):

- `GetQueueGlobalSummaryUseCase` — инжектит репозитории + `QueueInspectorPort`, агрегирует счётчики
- `GetQueueOrderUseCase` — инжектит `QueueInspectorPort` + `SourceRepositoryPort` (для title), маппит в DTO
- `GetQueueFailedUseCase` — инжектит репозитории, вызывает `get_failed_grouped_by_error`, маппит в DTO
- `RetryQueueUseCase` — инжектит репозитории (для поиска candidate_ids по error) + существующие enqueue use cases, делегирует retry
- `CancelQueueUseCase` — инжектит `QueueInspectorPort` + репозитории (для обновления статуса в БД)

**Infrastructure routes** (`infrastructure/api/routes/`):

- `queue.py` — новый роутер, монтируется в app. Тонкий слой: парсит параметры, вызывает use case, возвращает DTO.

**DI** (`infrastructure/container.py`):

- Регистрация `ArqQueueInspector` как реализации `QueueInspectorPort`
- Фабрики для новых use cases

### Source processing как «job»

Сейчас processing запускается через `asyncio.create_task()` в endpoint'е, а не через arq. Для отображения на экране очереди:
- **Running**: sources со `status == PROCESSING` — уже есть в БД, просто читаем
- **Failed**: sources со `status == ERROR` — уже есть в БД + `error_message`
- **Queued**: нет понятия «queued processing» сейчас — processing запускается немедленно. Оставляем как есть, показываем только running и failed
- **Retry**: для failed processing — вызов существующего `/sources/{id}/process` endpoint'а
- **Cancel**: для running processing — сейчас нет механизма отмены `asyncio.create_task`. Вариант: добавить CancellationToken/Event. Оставить как TODO — на первой итерации cancel processing не поддерживается, кнопка не показывается.

### YouTube DL как «job»

YouTube download идёт через arq (`download_youtube_video`). Уже есть в Redis-очереди, уже поддерживает abort. Полностью вписывается в общую схему. Для определения failed: sources с `content_type == YOUTUBE` и `status == ERROR` где `error_message` содержит ошибку загрузки.

---

## Frontend

### Новый роут

`/queue` → `QueuePage` — добавить в `App.tsx` и в навигацию.

### Компоненты

- `QueuePage` — контейнер, управляет фильтром и polling
- `QueueFilter` — dropdown с источниками (только те, у которых есть активность)
- `QueueGlobalActions` — кнопки Retry All Failed / Cancel All Queued
- `JobTypeBlock` — блок одного типа job'а (счётчики + retry/cancel)
- `QueueOrderList` — плоский FIFO-список (running + queued секции)
- `QueueJobRow` — строка одного job'а (badge + source + cancel)
- `FailedSection` — секция ошибок
- `FailedJobTypeGroup` — группа ошибок одного типа job'а
- `FailedErrorRow` — строка одного типа ошибки (текст + count + sources + retry)

### Polling

Переиспользовать паттерн из `useSourcePolling.ts`. Интервал: 2 секунды. Три параллельных запроса:
- `GET /api/queue/global-summary?source_id=...`
- `GET /api/queue/order?source_id=...&limit=50`
- `GET /api/queue/failed?source_id=...`

Polling активен всегда пока страница открыта (очередь живая).

### Цветовое кодирование типов

Каждый тип job'а — свой цвет badge'а для быстрого визуального различения в списке очереди:
- YouTube DL — фиолетовый
- Processing — зелёный
- Meanings — жёлтый
- Media — голубой
- Pronunciation — бирюзовый

---

## Тестирование

### Backend unit-тесты

**Use cases** (mock порты):
- `GetQueueGlobalSummaryUseCase`: корректная агрегация счётчиков из всех репозиториев + `QueueInspectorPort`; фильтрация по `source_id`; пустая очередь → все нули
- `GetQueueOrderUseCase`: корректный порядок из `QueueInspectorPort`; фильтрация по `source_id`; `limit` обрезает список; `total_queued` не зависит от `limit`
- `GetQueueFailedUseCase`: группировка по типу job'а → типу ошибки; фильтрация по `source_id` убирает breakdown по источникам; пустой список если нет failed
- `RetryQueueUseCase`: retry all failed для типа; retry по конкретному `error_text`; retry с `source_id` фильтром; processing retry вызывает process source
- `CancelQueueUseCase`: cancel per-job по `job_id`; cancel по типу; cancel с `source_id`; cancel обновляет статус в БД

**Adapters**:
- `ArqQueueInspector`: парсинг job_id → job_type + source_id; сортировка по score; фильтрация по source_id; пустая очередь

**Repositories** (новые методы, тест на реальной SQLite):
- `count_by_status_global`: считает по всем источникам; считает по одному source_id; возвращает 0 при отсутствии
- `get_failed_grouped_by_error`: группирует одинаковые ошибки; разбивает по источникам; не включает non-failed
- `get_candidate_ids_by_error`: возвращает только кандидаты с указанной ошибкой

### Backend integration-тесты

- E2E через HTTP: `GET /api/queue/global-summary` → корректный JSON с пятью типами
- E2E: `POST /api/queue/retry` → failed кандидаты переходят в queued
- E2E: `POST /api/queue/cancel` → queued кандидаты переходят в cancelled
- E2E: фильтрация по `source_id` возвращает данные только по этому источнику

### Frontend

- Визуальная проверка в браузере: открыть `/queue`, убедиться что данные отображаются
- Проверить фильтрацию по источнику
- Проверить retry/cancel кнопки — вызывают правильные API

---

## Разработка

Вести в git worktree (отдельная ветка `feat/queue-management`).

---

## Что НЕ делаем (сознательные ограничения)

- **Cancel running processing** — нет механизма отмены `asyncio.create_task`, добавлять CancellationToken — отдельная задача
- **Переупорядочивание очереди** — arq не поддерживает изменение порядка в ZSET, и UX для этого сложный
- **Пагинация failed** — на первой итерации показываем все группы ошибок. Если их станет много — добавим позже
- **Realtime (WebSocket)** — polling каждые 2 секунды достаточен для MVP
