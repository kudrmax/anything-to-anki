# Cambridge Pronunciation Audio on Anki Cards

**Дата:** 2026-04-19
**Задача:** tasks_cambridge.md #1 — Audio на карточках

---

## Цель

Добавить произношение target-слова из Cambridge Dictionary на карточки Anki. Два новых поля: `AudioTargetUS` (American English) и `AudioTargetUK` (British English). Источник — mp3 URL-ы из `cambridge.jsonl` (покрытие US 92.9%, UK 68.7%).

---

## Решения

| Вопрос | Решение |
|--------|---------|
| Где на карточке | Два новых поля `AudioTargetUS`, `AudioTargetUK` (отдельно от фразового `Audio`) |
| UK vs US | Оба, в разных полях |
| Когда скачивать | По кнопке пользователя, через arq-очередь (как meaning/media) |
| Хранение файлов | По кандидату: `{media_root}/{source_id}/{candidate_id}_pron_us.mp3` |
| Дедупликация | Не нужна — дублирование допустимо, ситуация редкая |
| Гранулярность job | Один job на кандидата (скачивает US + UK) |
| Нет аудио в Cambridge | Пустое поле, ничего не скачиваем |

---

## Архитектура

Новый enrichment step по аналогии с `CandidateMedia` и `CandidateMeaning`.

### Domain Layer

**Entity: `CandidatePronunciation`** (`domain/entities/candidate_pronunciation.py`)

Frozen dataclass:

- `candidate_id: int` — PK, 1:1 с кандидатом
- `us_audio_path: str | None` — путь к скачанному US mp3
- `uk_audio_path: str | None` — путь к скачанному UK mp3
- `status: EnrichmentStatus` — IDLE / QUEUED / RUNNING / DONE / FAILED / CANCELLED
- `error: str | None`
- `generated_at: datetime | None`

**Port: `CandidatePronunciationRepository`** (`domain/ports/candidate_pronunciation_repository.py`)

ABC, по аналогии с `CandidateMediaRepository`:

- `get_by_candidate_id(candidate_id) -> CandidatePronunciation | None`
- `get_by_candidate_ids(candidate_ids) -> dict[int, CandidatePronunciation]`
- `upsert(pronunciation) -> None`
- `get_eligible_candidate_ids(source_id) -> list[int]` — кандидаты со статусом PENDING/LEARN, у которых ещё нет произношения
- `mark_queued_bulk(candidate_ids) -> None`
- `mark_running(candidate_id) -> None`
- `mark_failed(candidate_id, error) -> None`
- `mark_batch_cancelled(candidate_ids) -> None`
- `fail_all_running(error) -> int` — startup reconciliation
- `get_candidate_ids_by_status(source_id, status) -> list[int]`

**Port: `PronunciationSource`** (`domain/ports/pronunciation_source.py`)

ABC для lookup URL-ов произношения по lemma:

- `get_audio_urls(lemma: str) -> tuple[str | None, str | None]` — возвращает (us_url, uk_url)

Позволяет подменить источник (сейчас Cambridge, потом другой словарь).

### Application Layer

**Use Case: `DownloadPronunciationUseCase`** (`application/use_cases/download_pronunciation.py`)

Метод `execute_one(candidate_id: int) -> None`:

1. Загрузить кандидата, получить lemma
2. Вызвать `PronunciationSource.get_audio_urls(lemma)` — получить US/UK URL-ы
3. Если оба None — upsert с DONE и пустыми путями (слова нет в Cambridge)
4. Скачать mp3 по URL-ам (httpx/urllib) в `{media_root}/{source_id}/{candidate_id}_pron_us.mp3` и `..._pron_uk.mp3`
5. Проверить что статус всё ещё RUNNING (мог быть CANCELLED)
6. Upsert с DONE, путями, generated_at

Ошибки:
- HTTP-ошибки скачивания → mark_failed с описанием
- Отмена пользователем → mark_batch_cancelled

**Use Case: `EnqueuePronunciationDownloadUseCase`** (`application/use_cases/enqueue_pronunciation_download.py`)

Метод `execute(source_id: int) -> list[int]`:

1. Получить eligible candidate IDs
2. mark_queued_bulk
3. Вернуть список ID для enqueue в arq

**DTO расширения:**

- `CardPreviewDTO`: добавить `pronunciation_us_url: str | None`, `pronunciation_uk_url: str | None`
- `QueueSummaryDTO`: добавить секцию `pronunciation` (queued/running/done/failed/cancelled counts)

### Infrastructure Layer

**Adapter: `CambridgePronunciationSource`** (`infrastructure/adapters/cambridge/pronunciation_source.py`)

Реализует порт `PronunciationSource`. При инициализации загружает `cambridge.jsonl` через существующий `parse_cambridge_jsonl()`. Метод `get_audio_urls(lemma)`:

1. Найти слово в словаре
2. Взять первый entry с непустым `us_audio` / `uk_audio`
3. Вернуть (us_url, uk_url) или (None, None)

**SQLAlchemy Model: `CandidatePronunciationModel`** (`infrastructure/persistence/models.py`)

Таблица `candidate_pronunciations`:

- `candidate_id: Integer, PK, FK → candidates.id`
- `us_audio_path: Text, nullable`
- `uk_audio_path: Text, nullable`
- `status: String(20), not null, default "done"`
- `error: Text, nullable`
- `generated_at: DateTime, nullable`

**Repository: `SqlaCandidatePronunciationRepository`** (`infrastructure/persistence/sqla_candidate_pronunciation_repository.py`)

Реализует порт. По аналогии с `SqlaCandidateMediaRepository`.

**Alembic Migration:** `0015_add_candidate_pronunciations_table.py` (или следующий номер)

**Worker Job: `download_pronunciation_for_candidate`** (`infrastructure/workers.py`)

Добавить в `WorkerSettings.functions`. Паттерн:
1. mark_running в отдельной сессии
2. Проверить что статус RUNNING
3. `asyncio.to_thread(use_case.execute_one, candidate_id)`
4. Error handling: CancelledError → cancel, PermanentError → fail, Exception → fail

Startup reconciliation: `pronunciation_repo.fail_all_running("interrupted by worker restart")`

**API Endpoints** (`infrastructure/api/routes/pronunciation.py`):

- `POST /sources/{source_id}/pronunciation/generate` (202) — enqueue download jobs
- `POST /sources/{source_id}/pronunciation/cancel` — cancel queued/running
- `POST /sources/{source_id}/pronunciation/retry-failed` (202) — retry failed
- `GET /media/{source_id}/{filename}` — уже существует, mp3 отдаются через тот же endpoint

**Container.py:**

- Добавить `CambridgePronunciationSource` (singleton, загружает cambridge.jsonl один раз)
- Добавить `SqlaCandidatePronunciationRepository`
- Добавить `DownloadPronunciationUseCase`
- Добавить `EnqueuePronunciationDownloadUseCase`

### Sync to Anki

В `SyncToAnkiUseCase`:

1. Добавить настройки `anki_field_audio_target_us`, `anki_field_audio_target_uk` (defaults: `"AudioTargetUS"`, `"AudioTargetUK"`)
2. При сборке note: если поле настроено и `pronunciation.us_audio_path` существует — `store_media_file()` + `[sound:{filename}]`
3. Поля добавить в default fields списка note type

### Frontend

**ReviewPage.tsx:**

- Кнопка "Download Pronunciation" рядом с "Generate Media"
- Polling: добавить pronunciation в проверку inflight jobs
- Cancel/Retry кнопки

**CandidateCardV2.tsx:**

- Отображение иконки/кнопки воспроизведения для US/UK произношения
- Статус загрузки (spinner/error) по аналогии с media

**API client:**

- `enqueuePronunciationDownload(sourceId, sortOrder)`
- `cancelPronunciationDownload(sourceId)`
- `retryFailedPronunciation(sourceId)`

---

## Файловая структура изменений

```
backend/src/backend/
├── domain/
│   ├── entities/candidate_pronunciation.py          # NEW
│   └── ports/
│       ├── candidate_pronunciation_repository.py    # NEW
│       └── pronunciation_source.py                  # NEW
├── application/
│   ├── use_cases/
│   │   ├── download_pronunciation.py                # NEW
│   │   └── enqueue_pronunciation_download.py        # NEW
│   └── dto/anki_dtos.py                             # EDIT: add pronunciation fields
├── infrastructure/
│   ├── adapters/cambridge/pronunciation_source.py   # NEW
│   ├── persistence/
│   │   ├── models.py                                # EDIT: add CandidatePronunciationModel
│   │   └── sqla_candidate_pronunciation_repository.py # NEW
│   ├── workers.py                                   # EDIT: add job + startup reconciliation
│   ├── api/routes/pronunciation.py                  # NEW
│   ├── container.py                                 # EDIT: wire dependencies
│   └── api/routes/anki.py                           # EDIT: register new router
├── alembic/versions/XXXX_add_candidate_pronunciations.py  # NEW

frontends/web/src/
├── api/
│   ├── client.ts                                    # EDIT: add pronunciation API calls
│   └── types.ts                                     # EDIT: add pronunciation fields
├── pages/ReviewPage.tsx                             # EDIT: add button + polling
└── components/CandidateCardV2.tsx                   # EDIT: playback UI
```

---

## Что НЕ входит в scope

- TTS fallback для слов без аудио в Cambridge — отдельная задача
- IPA из Cambridge (#4 в tasks_cambridge.md) — отдельная задача
- Выбор sense-specific произношения (Cambridge audio привязано к headword, не к sense)
- Кэширование/дедупликация mp3 между source'ами
