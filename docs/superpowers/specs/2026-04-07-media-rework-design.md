# Media Rework — Design Spec

**Date:** 2026-04-07
**Status:** Approved (pending review)

## Goal

Переработать пайплайн медиа (скриншоты + аудио) от извлечения до экспорта в Anki: встроенный показ в карточках кандидатов вместо hover-popover, batch-генерация из ReviewPage, сжатие в WebP/AAC, управление хранилищем, и авто-реконциляция диска и БД.

## Scope

Одна цельная задача — жизненный цикл медиа:

1. **UI:** перенос "Generate media" в ReviewPage, встроенный показ в карточках, исправление модалки выбора дорожек
2. **Generation:** batch по learn+pending (skip existing), per-candidate регенерация с пересчётом timecodes
3. **Compression:** WebP для картинок, AAC/M4A для аудио
4. **Anki export:** поля `Image` / `Audio` с сжатыми файлами
5. **Storage management:** Settings-страница с таблицей размеров и кнопками очистки
6. **Reconciliation:** orphan cleanup на старте + lazy cleanup при 404 в рантайме
7. **Bug fix:** перекрытие тулбара карточки (auto-resolved при новом layout)

Не в скоупе:
- Автоматическая регенерация аудио при редактировании границ фрагмента (делается по кнопке вручную)
- Backfill старых JPG/MP3 файлов в новый формат (пользователь может удалить и перегенерировать через Settings)

## Architecture

### Компоненты

```
┌─────────────────────────────────────────────────────────────┐
│  ReviewPage                                                  │
│  [Generate Meanings] [Generate Media]  ← две batch кнопки   │
│                                                              │
│  CandidateCardV2 (layout B — horizontal split):             │
│  ┌──────────────┬──────────────────────────────────┐       │
│  │  Screenshot  │  Fragment + Meaning + Actions    │       │
│  │  160×90 (css)│  [Learn] [Known] [Skip]          │       │
│  │  ▶ Play 0:03 │  toolbar: edit/ai/info/🎬regen  │       │
│  └──────────────┴──────────────────────────────────┘       │
│   (stored as 640×360 webp, CSS-scaled to 160×90 in card)   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Backend                                                     │
│                                                              │
│  Use Cases:                                                  │
│   • RunMediaExtractionJobUseCase — batch, skip existing     │
│   • RegenerateCandidateMediaUseCase — per-candidate, НОВЫЙ  │
│   • CleanupMediaUseCase — НОВЫЙ (для Settings page)         │
│   • GetMediaStorageStatsUseCase — НОВЫЙ                     │
│                                                              │
│  Adapters:                                                   │
│   • FfmpegMediaExtractor — теперь пишет webp и m4a          │
│   • AnkiConnectConnector — store_media_file для webp/m4a    │
│                                                              │
│  Infrastructure:                                             │
│   • reconcile_media_files() — startup: orphan cleanup       │
│   • LazyMediaReconciler — runtime: async cleanup on 404     │
└─────────────────────────────────────────────────────────────┘
```

### Data flow — per-candidate regeneration

```
User clicks 🎬 on candidate card
  ↓
POST /candidates/{id}/regenerate-media
  ↓
RegenerateCandidateMediaUseCase.execute(candidate_id):
  1. Load candidate + source
  2. Parse source.raw_text via structured_srt_parser.parse_structured()
  3. Recompute (start_ms, end_ms) = find_timecodes(candidate.context_fragment, parsed)
     ← even if fragment was edited since last extraction
  4. Update candidate.media_start_ms/end_ms in DB
  5. ffmpeg: regenerate audio (new timecodes) + screenshot (new midpoint)
     → overwrites existing files at same path (or new extension webp/m4a)
  6. Commit
```

## Components

### 1. UI: перенос "Generate media" в ReviewPage (~150 words)

**InboxPage.tsx:**
- Убрать логику `mediaJobs` state, polling, prop `mediaJob` из `<SourceCard>`
- Убрать `handleGenerateMedia` handler и prop `onGenerateMedia`

**SourceCard.tsx:**
- Убрать условный рендер блока с кнопкой/статусом "Generate media" (строки с `source.source_type === 'video' && ...`)
- Убрать prop `onGenerateMedia` и `mediaJob` из интерфейса
- Убрать импорт `Film` из lucide-react

**ReviewPage.tsx:**
- Перенести `mediaJobs` state и polling сюда (но теперь для одного source)
- Добавить handler `handleGenerateMedia()` — вызывает `api.startMediaExtraction(sourceId)`
- Рядом с кнопкой `Sparkles + "Generate Meanings"` добавить вторую кнопку `Film + "Generate Media"`
- Показывать эту кнопку только если `source.source_type === 'video'`
- Такая же логика состояний: running/done/failed через бейджи

### 2. Batch-генерация для learn+pending (~120 words)

**StartMediaExtractionUseCase** (`manage_media_extraction.py`):
- Изменить фильтр eligible: `c.status in (LEARN, PENDING)` вместо только `LEARN`
- Сохранить условие `c.screenshot_path is None` — это реализация "skip existing" (вариант A)
- Сохранить условие `media_start_ms is not None` (candidate должен иметь timecodes)
- Логировать: total, by_status (learn/pending), eligible (без медиа), already_has_media

Пример лога:
```
StartMediaExtraction source=27: 89 total, 12 learn, 77 pending, 89 eligible, 0 already_has_media
```

### 3. Per-candidate регенерация (~180 words)

**Новый use case** `RegenerateCandidateMediaUseCase`:

```python
class RegenerateCandidateMediaUseCase:
    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        structured_srt_parser: StructuredSrtParser,
        media_extractor: MediaExtractor,
        media_root: str,
    ) -> None: ...

    def execute(self, candidate_id: int) -> None:
        # 1. Load candidate and source
        # 2. If source.source_type != VIDEO → raise ValueError
        # 3. Parse source.raw_text → ParsedSrt
        # 4. Recompute timecodes:
        #    timecodes = find_timecodes(candidate.context_fragment, parsed)
        #    if timecodes is None → raise ValueError (fragment not in SRT)
        # 5. Update candidate.media_start_ms/end_ms
        # 6. Generate paths (webp/m4a extensions)
        # 7. Extract screenshot at midpoint
        # 8. Extract audio with source.audio_track_index
        # 9. Update candidate.screenshot_path/audio_path
```

**API endpoint:** `POST /candidates/{candidate_id}/regenerate-media` → 202

**UI button в CandidateCardV2 toolbar** — иконка `RefreshCw` рядом с Sparkles (AI gen). Видна всегда когда `source.source_type === 'video'` и candidate имеет `media_start_ms` (т.е. фрагмент ложится на SRT). Используется и для первичной генерации отдельного кандидата, и для перегенерации после редактирования фрагмента — логика одна. Disabled во время выполнения запроса.

**Связь с batch-кнопкой:** batch "Generate media" вызывает извлечение скопом; per-candidate кнопка — точечное действие. Они дополняют друг друга, не конкурируют. Batch всегда skip existing; per-candidate всегда регенерирует (с recompute timecodes).

### 4. Compression (~150 words)

**FfmpegMediaExtractor.extract_screenshot:**
```python
args = [
    "ffmpeg", "-y",
    "-ss", str(ts_s),
    "-i", video_path,
    "-vframes", "1",
    "-vf", "scale='min(640,iw)':'-2'",  # max 640px wide, -2 keeps aspect, even number
    "-c:v", "libwebp",
    "-quality", "75",
    out_path,  # extension .webp
]
```

**FfmpegMediaExtractor.extract_audio:**
```python
args = [
    "ffmpeg", "-y",
    "-ss", str(start_s),
    "-to", str(end_s),
    "-i", video_path,
    "-vn",
]
if audio_track_index is not None:
    args += ["-map", f"0:a:{audio_track_index}"]
args += [
    "-c:a", "aac",
    "-b:a", "96k",
    "-ac", "1",           # mono
    out_path,  # extension .m4a
]
```

**Пути в `RunMediaExtractionJobUseCase`:**
```python
screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.webp")
audio_path      = os.path.join(out_dir, f"{candidate_id}_audio.m4a")
```

### 5. Anki export с полями Image/Audio (~100 words)

**sync_to_anki.py:**
- Переименовать константу `_DEFAULT_FIELD_SCREENSHOT = "Image"` (было "Screenshot")
- Поле настроек `"anki_field_screenshot"` → `"anki_field_image"`
- Ноут-тип `AnythingToAnkiType` при авто-создании получает поля: `Sentence, Target, Meaning, IPA, Image, Audio`
- В цикле `sync_to_anki`:
    ```python
    if candidate.screenshot_path and os.path.exists(candidate.screenshot_path):
        filename = os.path.basename(candidate.screenshot_path)
        self._connector.store_media_file(filename, candidate.screenshot_path)
        note[field_image] = f'<img src="{filename}">'
    ```
- `store_media_file` уже существует в AnkiConnector port — не меняем

### 6. Settings: Media Storage section (~200 words)

**Новый use case** `GetMediaStorageStatsUseCase`:

```python
@dataclass(frozen=True)
class SourceMediaStats:
    source_id: int
    source_title: str
    screenshot_bytes: int
    audio_bytes: int
    screenshot_count: int
    audio_count: int

class GetMediaStorageStatsUseCase:
    def execute(self) -> list[SourceMediaStats]:
        # Iterate all video sources, os.stat() their media files, aggregate
```

**Новый use case** `CleanupMediaUseCase`:

```python
class CleanupMediaKind(Enum):
    ALL = "all"
    IMAGES = "images"
    AUDIO = "audio"

class CleanupMediaUseCase:
    def execute(self, source_id: int, kind: CleanupMediaKind) -> None:
        # 1. Load candidates of source
        # 2. For each: delete file from disk (if matches kind)
        # 3. Clear screenshot_path/audio_path in DB (if matches kind)
        # 4. If ALL and source folder empty → rmdir
```

**API endpoints:**
- `GET /settings/media-stats` → `list[SourceMediaStats]`
- `POST /settings/media-cleanup` body `{source_id, kind: "all"|"images"|"audio"}` → 204

**SettingsPage UI:**
- Новая секция "Media storage" в существующей странице настроек
- Таблица: `Source title | Images (size) | Audio (size) | Actions`
- Actions: три иконки-кнопки с подтверждением `confirm()`
- Total строка снизу: суммарные размеры
- Refresh button для обновления статистики

### 7. Reconciliation + Delete-source cleanup (~250 words)

**DeleteSourceUseCase extension (часть A выбора C = A+B):**

Добавить шаг в `DeleteSourceUseCase.execute()`:
```python
def execute(self, source_id: int) -> None:
    # existing: delete candidates, sync records, etc.
    ...
    # NEW: remove media directory for this source
    media_dir = os.path.join(self._media_root, str(source_id))
    if os.path.isdir(media_dir):
        shutil.rmtree(media_dir, ignore_errors=True)
        logger.info("Deleted media directory %s", media_dir)
    # then: delete source row itself
```

`DeleteSourceUseCase` получает `media_root` через конструктор (wiring в container). Это закрывает основную дыру — при удалении source больше не остаётся файлов-мусора.

**Startup — `reconcile_media_files(session_factory, media_root)`:**

Две фазы:

**Фаза 1 — orphan files на диске:**
```python
# Список всех папок в media_root
for source_dir in os.listdir(media_root):
    if not source_dir.isdigit(): continue
    source_id = int(source_dir)
    source = source_repo.get_by_id(source_id)
    if source is None:
        shutil.rmtree(os.path.join(media_root, source_dir))
        logger.info("Reconcile: removed orphan dir %s", source_dir)
        continue

    # Для каждого файла в валидной папке
    for fname in os.listdir(os.path.join(media_root, source_dir)):
        match = re.match(r"(\d+)_(screenshot|audio)\.", fname)
        if not match:
            continue  # unknown file, leave it
        candidate_id = int(match.group(1))
        kind = match.group(2)
        candidate = candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            os.remove(os.path.join(media_root, source_dir, fname))
            logger.info("Reconcile: removed orphan file %s", fname)
```

Вызов в `lifespan()` рядом с `resume_media_extraction_jobs`.

**Runtime — `LazyMediaReconciler`:**

Singleton service в Container:
```python
class LazyMediaReconciler:
    def __init__(self, session_factory, media_root) -> None:
        self._session_factory = session_factory
        self._media_root = media_root
        self._in_progress: set[int] = set()
        self._lock = asyncio.Lock()

    async def schedule(self, source_id: int) -> None:
        async with self._lock:
            if source_id in self._in_progress:
                return
            self._in_progress.add(source_id)
        asyncio.create_task(self._reconcile_source(source_id))

    async def _reconcile_source(self, source_id: int) -> None:
        try:
            session = self._session_factory()
            # SELECT candidates WHERE source_id = ? AND (screenshot_path IS NOT NULL OR audio_path IS NOT NULL)
            # For each: os.path.exists on paths, UPDATE NULL if missing
            # Log: "LazyReconcile source=%d: cleared %d screenshot, %d audio"
        finally:
            async with self._lock:
                self._in_progress.discard(source_id)
            session.close()
```

**Media route `/media/{source_id}/{filename}` — must convert to async:**

Текущий роут — sync (`def serve_media_file`). Для использования `asyncio` в reconciler — переводим на async:

```python
@router.get("/media/{source_id}/{filename}")
async def serve_media_file(
    source_id: int,
    filename: str,
    container: Container = Depends(get_container),
) -> FileResponse:
    file_path = os.path.join(container.media_root(), str(source_id), filename)
    if not os.path.exists(file_path):
        await container.lazy_media_reconciler().schedule(source_id)
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)
```

`FileResponse` работает и в async-роутах. Других изменений не требуется.

### 8. Modal visual fix (~50 words)

В `InboxPage.tsx` track selection modal:
- Оверлей: `background: rgba(0,0,0,0.7)` + `backdropFilter: blur(8px)`
- Карточка: `background: #1a1d2e` (сплошной) вместо `var(--bg)`
- Убедиться что `z-index` оверлея перекрывает всё остальное

### 9. Bug fix: toolbar overlap

Resolved automatically — при layout B popover исчезает совсем, медиа встраивается в карточку, тулбар больше ничем не перекрывается.

## Data Models

### No schema changes needed

Все существующие поля переиспользуются:
- `candidates.screenshot_path TEXT` (теперь будет .webp)
- `candidates.audio_path TEXT` (теперь будет .m4a)
- `candidates.media_start_ms INTEGER`
- `candidates.media_end_ms INTEGER`

Формат хранится "в расширении файла", не в БД.

## Error Handling

- **ffmpeg fails (webp/m4a unsupported):** ffmpeg в наш Docker image уже собран с `--enable-libwebp` и `--enable-aac` (проверить перед реализацией). Если нет — добавить в Dockerfile.
- **File missing during regeneration:** `FileNotFoundError` → 500 с понятным сообщением
- **Fragment не находится в SRT при регенерации:** `ValueError("Fragment not found in subtitles")` → 400
- **Source deleted during lazy reconcile:** try/except вокруг SELECT, логируем и выходим
- **Cleanup on non-video source:** `ValueError("Source is not a video")` → 400

## Testing

### Unit tests
- `test_regenerate_candidate_media.py` — new use case, мок `StructuredSrtParser`/`MediaExtractor`, проверить что timecodes пересчитаны
- `test_cleanup_media.py` — new use case, `tmp_path` для реальных файлов, проверить удаление файлов + обнуление БД
- `test_get_media_storage_stats.py` — агрегация по source
- `test_reconcile_media_files.py` — два прохода с `tmp_path` и моками репозиториев
- `test_lazy_media_reconciler.py` — дедупликация через `asyncio.Lock`, async timing
- Обновить `test_run_media_extraction_job.py` — теперь eligible включает PENDING статус
- Обновить `test_sync_to_anki.py` — поле Image вместо Screenshot

### Integration tests
- `test_media_routes_404.py` — GET несуществующий файл → 404 + scheduled reconcile
- `test_cleanup_endpoints.py` — POST cleanup различных kind

## Migrations

- **CSS переменные:** ни одна новая не добавляется
- **DB schema:** изменений нет
- **Settings keys:** один переименован `anki_field_screenshot` → `anki_field_image`. Миграция в `upgrade_schema`:
  ```python
  conn.execute(text(
      "UPDATE settings SET key = 'anki_field_image' WHERE key = 'anki_field_screenshot'"
  ))
  ```

## Rollout

Порядок реализации (задачи в следующем плане):
1. Backend compression (ffmpeg config) + tests
2. Backend reconciliation (startup + lazy) + tests
3. Backend use cases (regenerate, cleanup, stats) + tests
4. Backend API endpoints
5. Frontend ReviewPage batch button перенос
6. Frontend CandidateCardV2 layout B
7. Frontend per-candidate regenerate button
8. Frontend SettingsPage media storage section
9. Frontend track selection modal visual fix
10. Anki export поля Image/Audio
11. End-to-end smoke test с реальным видео
