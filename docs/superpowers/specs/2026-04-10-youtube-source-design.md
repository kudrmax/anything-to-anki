# YouTube как источник — Design Spec

**Дата:** 2026-04-10
**Статус:** Draft

## Контекст

AnythingToAnki поддерживает 4 типа источников: TEXT, LYRICS, SUBTITLES, VIDEO (локальный файл). YouTube — самый частый сценарий для language learners, и его нет. Заодно с добавлением YouTube проводим рефакторинг: разделяем `SourceType` на два слоя (`InputMethod` + `ContentType`), чтобы расширяемо поддерживать новые способы ввода (Genius, статьи и т.д.) без роста ветвлений в pipeline.

## Решения (согласованы с пользователем)

1. **Полный pipeline:** субтитры + аудио + скриншоты (как для локального видео)
2. **Lazy download:** субтитры скачиваются сразу при создании, видео — по запросу пользователя (кнопка "Download Media")
3. **Cleanup:** после генерации всех медиа скачанное видео автоматически удаляется
4. **Нет субтитров:** ошибка «Субтитры для видео не получилось получить», источник не создаётся
5. **Язык субтитров:** всегда английский, без выбора
6. **Архитектура URL:** расширяемая — YouTube первый, но не последний URL-тип

## Двухуровневая типизация источников

### InputMethod (заменяет SourceType)

Отвечает на вопрос **«как контент попал в систему»**. Определяет логику ingestion: какой адаптер вызвать, что парсить, откуда скачать.

```python
class InputMethod(StrEnum):
    TEXT_PASTED = "text_pasted"
    LYRICS_PASTED = "lyrics_pasted"
    SUBTITLES_FILE = "subtitles_file"
    VIDEO_FILE = "video_file"
    YOUTUBE_URL = "youtube_url"
```

### ContentType (новый)

Отвечает на вопрос **«что это для pipeline и review»**. Определяет парсер, наличие timecodes, возможность media extraction, UI review.

```python
class ContentType(StrEnum):
    TEXT = "text"
    LYRICS = "lyrics"
    VIDEO = "video"
```

### Маппинг

Чистая функция в domain layer. Вызывается один раз при создании источника, результат сохраняется в `content_type`.

```
InputMethod          →  ContentType
─────────────────────────────────────
text_pasted          →  text
lyrics_pasted        →  lyrics
subtitles_file       →  text      # SRT без видео — просто текст
video_file           →  video
youtube_url          →  video
```

### Принцип использования

- **InputMethod** — используется при ingestion (создание источника, выбор адаптера загрузки)
- **ContentType** — используется в pipeline (`ProcessSourceUseCase`, парсеры, timecode mapping, media extraction) и в UI review
- `ProcessSourceUseCase.source_parsers` перекеивается с `SourceType` на `ContentType`
- Все ветвления в pipeline по `source.source_type` заменяются на `source.content_type`

## Изменения в БД

Одна Alembic-миграция:

| Действие | Колонка | Тип | Описание |
|---|---|---|---|
| Переименовать | `source_type` → `input_method` | String(20) | Новое имя |
| Миграция данных | `input_method` | — | `text`→`text_pasted`, `lyrics`→`lyrics_pasted`, `subtitles`→`subtitles_file`, `video`→`video_file` |
| Добавить | `content_type` | String(10) NOT NULL | `text` / `lyrics` / `video` |
| Добавить | `source_url` | Text, nullable | YouTube URL (и будущие URL-источники) |

Таблица `candidate_media` — без изменений.

## Domain Layer

### Source entity

```python
@dataclass
class Source:
    input_method: InputMethod        # было source_type
    content_type: ContentType        # новое, вычисляется из input_method при создании
    source_url: str | None = None    # YouTube URL (и будущие URL-источники)
    # raw_text, title, cleaned_text, status, error_message,
    # processing_stage, video_path, audio_track_index, created_at — без изменений
```

### Порт: UrlSourceFetcher

Расширяемый порт для обработки URL-источников. Каждый URL-тип — отдельная реализация.

```python
class UrlSourceFetcher(ABC):
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Может ли этот fetcher обработать данный URL."""

    @abstractmethod
    def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
        """Скачать субтитры. Бросает SubtitlesNotAvailableError если нет."""

@dataclass(frozen=True)
class FetchedSubtitles:
    srt_text: str
    title: str           # название видео с YouTube
    input_method: InputMethod  # youtube_url, genius_url, ...
```

### Порт: VideoDownloader

Отдельный порт для скачивания видео (отделён от fetcher'а субтитров, т.к. вызывается позже и асинхронно).

```python
class VideoDownloader(ABC):
    @abstractmethod
    def download(self, url: str, output_path: str) -> None:
        """Скачать видео по URL в указанный файл."""
```

## Infrastructure Layer

### YtDlpSubtitleFetcher (реализует UrlSourceFetcher)

- `can_handle()`: проверяет `youtube.com`, `youtu.be`
- `fetch_subtitles()`:
  1. `yt-dlp --list-subs <url>` — проверяет наличие английских субтитров
  2. Приоритет: ручные (`en`) > авто-сгенерированные (`en-orig`, `en`)
  3. `yt-dlp --write-sub --sub-lang en --convert-subs srt --skip-download` — скачивает только субтитры
  4. Также забирает title видео из метаданных
  5. Если субтитров нет — бросает `SubtitlesNotAvailableError`
- Зависимость: `yt-dlp` — добавить в Dockerfile и Dockerfile.worker

### YtDlpVideoDownloader (реализует VideoDownloader)

- `download()`:
  1. `yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" -o <output_path> <url>`
  2. Ограничение 1080p — баланс качества и размера
  3. Бросает ошибку если скачивание не удалось

### UrlSourceFetcherRegistry

Простой реестр fetcher'ов в `container.py`:

```python
fetchers: list[UrlSourceFetcher] = [YtDlpSubtitleFetcher(), ...]  # будущие fetcher'ы

def resolve(url: str) -> UrlSourceFetcher:
    for f in fetchers:
        if f.can_handle(url):
            return f
    raise UnsupportedUrlError(url)
```

## Application Layer

### CreateSourceFromUrlUseCase (новый)

Отдельный use case для URL-источников (не модификация существующего `CreateSourceUseCase`).

```
execute(url: str, title_override: str | None = None) -> Source:
    1. fetcher = registry.resolve(url)
    2. result = fetcher.fetch_subtitles(url)
    3. title = title_override or result.title
    4. content_type = resolve_content_type(result.input_method)
    5. source = Source(
           raw_text=result.srt_text,
           input_method=result.input_method,
           content_type=content_type,
           source_url=url,
           title=title,
           status=NEW,
       )
    6. source_repo.create(source)
    7. return source
```

При `SubtitlesNotAvailableError` — пробрасывает наверх, API возвращает ошибку.

### DownloadVideoUseCase (новый)

Отвечает за скачивание видео для YouTube-источников. Вызывается из worker job'а.

```
execute(source_id: int) -> None:
    1. source = source_repo.get(source_id)
    2. Валидация: source.source_url is not None, source.video_path is None
    3. output_path = f"{DATA_DIR}/videos/{uuid4()}.mp4"
    4. video_downloader.download(source.source_url, output_path)
    5. source.video_path = output_path
    6. source_repo.update(source)
```

### CleanupVideoUseCase (новый)

Удаляет скачанное видео после генерации всех медиа.

```
execute(source_id: int) -> None:
    1. source = source_repo.get(source_id)
    2. Проверить: все candidate_media для этого source в статусе DONE
    3. Если video_path существует и source.input_method == YOUTUBE_URL:
       4. Удалить файл (os.remove — это временный скачанный файл в data/videos/, не пользовательские данные; trash в контейнере недоступен)
       5. source.video_path = None
       6. source_repo.update(source)
```

Вызывается автоматически из worker job'а после последнего успешного `extract_media_for_candidate`.

### ProcessSourceUseCase — изменения

- Маршрутизация парсеров: ключ `source_parsers` меняется с `SourceType` на `ContentType`
- Проверка `source.source_type == SourceType.VIDEO` меняется на `source.content_type == ContentType.VIDEO`
- Логика pipeline не меняется — субтитры уже в `raw_text`, timecodes маппятся так же

## Worker Jobs

### download_youtube_video (новый)

```python
async def download_youtube_video(ctx: dict, source_id: int) -> None:
    # Паттерн как у extract_media_for_candidate:
    # 1. Выполнить DownloadVideoUseCase
    # 2. При ошибке — пометить source.error_message
```

Ставится в очередь при нажатии "Download Media" в UI (API endpoint).

### extract_media_for_candidate — изменение

После успешной extraction проверить: все ли candidate_media для данного source в статусе DONE? Если да и source.input_method == YOUTUBE_URL — вызвать `CleanupVideoUseCase`.

## API

### POST /sources/url (новый endpoint)

```
Request:  { "url": "https://youtube.com/watch?v=...", "title": "..." (optional) }
Response: { "id": 123, "status": "new" }
Error:    { "error": "subtitles_not_available", "message": "Субтитры для видео не получилось получить" }
```

Маршрутизация: вызывает `CreateSourceFromUrlUseCase`. Скачивание субтитров через yt-dlp занимает несколько секунд — это синхронная операция в рамках запроса (аналогично сохранению видеофайла в `POST /sources/video`).

### POST /sources/{id}/download-video (новый endpoint)

```
Response: { "status": "downloading" }
```

Ставит в очередь job `download_youtube_video`. Валидация: source.source_url заполнен, video_path is None.

### GET /sources/{id} — изменения в response

Добавить поля:
- `input_method` (вместо `source_type`)
- `content_type`
- `source_url`
- `video_downloaded: bool` — вычисляемое: `video_path is not None`

Frontend использует `input_method` + `video_downloaded` чтобы решить, показывать "Download Media" или "Generate Media".

## Frontend

### InboxPage — URL tab

- Существующая детекция YouTube URL уже на месте
- При submit: `POST /sources/url` с URL из поля ввода
- При ошибке `subtitles_not_available`: показать toast «Субтитры для видео не получилось получить»
- При успехе: добавить источник в список, можно перейти внутрь

### Source detail page — кнопки медиа

Логика кнопки зависит от `input_method` и `video_downloaded`:

| input_method | video_downloaded | Кнопка |
|---|---|---|
| `video_file` | true (всегда) | "Generate Media" |
| `youtube_url` | false | "Download Media" |
| `youtube_url` | true | "Generate Media" |
| остальные | — | нет кнопки медиа |

"Download Media" → `POST /sources/{id}/download-video` → polling статуса → кнопка меняется на "Generate Media".

### TypeScript types

```typescript
type InputMethod = 'text_pasted' | 'lyrics_pasted' | 'subtitles_file' | 'video_file' | 'youtube_url'
type ContentType = 'text' | 'lyrics' | 'video'
```

## Docker

Добавить `yt-dlp` в оба Dockerfile:

```dockerfile
RUN pip install yt-dlp
```

Либо через apt, если доступен. `yt-dlp` нужен и в app-контейнере (скачивание субтитров при создании), и в worker-контейнере (скачивание видео).

## Тестирование

- **Unit:** `resolve_content_type` — маппинг всех InputMethod
- **Unit:** `YtDlpSubtitleFetcher.can_handle` — YouTube URL patterns
- **Unit:** `CreateSourceFromUrlUseCase` — happy path, subtitles not available
- **Unit:** `DownloadVideoUseCase` — happy path, validation errors
- **Unit:** `CleanupVideoUseCase` — cleanup condition, skip if not all media done
- **Integration:** создание YouTube-источника → process → download video → generate media → cleanup video
- **Frontend:** URL tab submit flow, кнопка Download/Generate Media switching

## Scope — что НЕ входит

- Другие URL-типы (Genius, статьи) — только архитектура расширяемости
- Загрузка своего SRT к YouTube-видео (fallback при отсутствии субтитров)
- Выбор языка субтитров (захардкожен английский)
- Кэширование скачанных субтитров/видео между источниками
