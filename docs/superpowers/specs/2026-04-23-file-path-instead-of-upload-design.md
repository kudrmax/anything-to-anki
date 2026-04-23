# File Path Instead of Upload

## Проблема

Сейчас все файлы (включая видео) загружаются через браузерный multipart upload. Для текстовых файлов это терпимо — содержимое читается в `raw_text` в БД, копия на диске не остаётся. Но для видео файл сохраняется в `data/videos/` и хранится вечно (нужен позже для ffmpeg: скриншоты, аудио-фрагменты). На проде это привело к 23 GB в `data/videos/`.

Приложение работает строго локально (localhost + обычный Chromium). Нет причин копировать файлы — бэкенд может читать их напрямую с диска по пути.

## Решение

Заменить file upload (drag-and-drop / file picker) на текстовое поле ввода пути к файлу. Бэкенд получает путь, читает файл с диска самостоятельно.

**Ключевое изменение для видео:** `Source.video_path` хранит оригинальный путь на диске пользователя (например `/Users/maxos/Movies/film.mkv`), а не путь к копии в `data/videos/`. Если файл удалён/перемещён — ошибка при извлечении медиа, без последствий.

**Для YouTube видео ничего не меняется** — скачивание через yt-dlp в `data/videos/` остаётся как есть.

## UI: вкладка File

Текущее состояние: drop-зона + file picker, поддержка drag-and-drop, множественный выбор файлов.

Новое состояние: текстовое поле для пути к файлу.

```
┌─────────────────────────────────────┐
│  File path                          │
│  [/Users/maxos/Movies/film.mkv    ] │
│                                     │
│  ↳ Subtitles (.srt) — optional      │  ← только для видео
│  [                                ] │
│                                     │
│  [+ Add source]                     │
└─────────────────────────────────────┘
```

- Одно основное поле — путь к любому файлу (видео, epub, html, txt, srt)
- Если расширение файла — видео (.mp4, .mkv, .avi, .mov): появляется второе поле для опционального .srt
- Бейдж с определённым типом (как сейчас `detectedFileType`) — по расширению из пути
- Drag-and-drop удаляется полностью из вкладки File

## API: изменения

### Текстовые файлы (epub, html, txt, srt)

**Было:** `POST /sources/video` и обработка в route — multipart `UploadFile`.
**Для текстовых файлов** endpoint `POST /sources` уже принимает `raw_text`. Сейчас фронтенд читает файл в браузере и отправляет текст. Новый flow:

**Стало:** `POST /sources/file` — принимает `{ file_path: str, title?: str }`.

Бэкенд:
1. Проверяет что файл существует
2. Определяет тип по расширению
3. Читает содержимое в `raw_text`
4. Создаёт Source как обычно

### Видеофайлы

**Было:** `POST /sources/video` — multipart upload, бэкенд сохраняет видео в `data/videos/{uuid}.ext`.

**Стало:** `POST /sources/file` — тот же endpoint, принимает `{ file_path: str, srt_path?: str, title?: str, subtitle_track_index?: int, audio_track_index?: int }`.

Бэкенд:
1. Проверяет что видеофайл существует по пути
2. Если передан `srt_path` — читает .srt с диска
3. Иначе — извлекает субтитры из видео (ffmpeg), как сейчас
4. Если несколько треков — возвращает `track_selection_required` (как сейчас)
5. Создаёт Source с `video_path = file_path` (оригинальный путь, без копирования)

### Удаляемый endpoint

`POST /sources/video` (multipart upload) — удаляется.

## Backend: изменения

### Route: `POST /sources/file`

Новый endpoint — тонкая обёртка, без логики. Заменяет `POST /sources/video`.

```python
@router.post("/sources/file")
async def create_file_source(
    body: FileSourceRequest,  # { file_path, srt_path?, title?, subtitle_track_index?, audio_track_index? }
) -> SourceCreatedResponse | TrackSelectionResponse:
    return use_case.execute_from_file(...)
```

Route не определяет тип файла и не читает содержимое — всё это делает use case.

### UseCase: `CreateSourceUseCase.execute_from_file()`

Новый метод, заменяет `execute_video()` и покрывает все типы файлов.

Логика:
1. Проверяет что файл существует по `file_path`
2. Определяет тип по расширению (видео vs текстовый)
3. Текстовый файл (epub, html, txt, srt) — читает содержимое через порт `FileReader`, создаёт Source с `raw_text`
4. Видео — работает как текущий `execute_video()`, но без копирования: `video_path = file_path` (оригинальный путь)
5. Если передан `srt_path` — читает .srt через тот же порт
6. Извлечение субтитров из видео, выбор треков — без изменений

### Порт: `FileReader`

Новый порт в `domain/ports/` — абстракция для чтения файлов с диска. Use case не читает файлы напрямую (это I/O).

```python
class FileReader(ABC):
    @abstractmethod
    def read_text(self, path: str) -> str: ...

    @abstractmethod
    def exists(self, path: str) -> bool: ...
```

Реализация в `infrastructure/adapters/` — тривиальная обёртка над `pathlib`.

### Обработка ошибок

При обращении к `video_path` (извлечение медиа, скриншоты, аудио) — если файл не найден:
- `MediaExtractionUseCase` уже должен проверять существование файла
- Возвращать понятную ошибку: "Video file not found at {path}"
- Фронтенд показывает ошибку в UI для медиа, остальные данные (текст, кандидаты) остаются доступны

## Frontend: изменения

### InboxPage.tsx — вкладка File

Убрать:
- `files` state (массив File объектов)
- `pendingVideoFile`, `pendingSrtFile` state
- Drag-and-drop обработчики (`handleGlobalDragOver`, `handleGlobalDrop`) для вкладки File
- File input (`<input type="file">`)
- File preview cards с кнопками удаления
- `detectedFileType()` на основе File объектов

Добавить:
- `filePath` state (string) — основное поле
- `srtPath` state (string) — поле для .srt (видимо только для видео)
- Определение типа по расширению из строки пути
- Бейдж с типом (как сейчас, но по расширению из строки)

### API client

Убрать `createVideoSource()` (multipart FormData upload).

Добавить `createFileSource(filePath, srtPath?, title?, subtitleTrackIndex?, audioTrackIndex?)` — обычный JSON POST.

### Track selection modal

Без изменений — модалка выбора треков остаётся, flow тот же. Разница: при повторном вызове после выбора треков передаём `file_path` (строку), а не `pendingVideoFile` (File объект).

## Что НЕ меняется

- YouTube flow — скачивание через yt-dlp в `data/videos/` остаётся
- URL tab — без изменений
- Text tab — без изменений
- `MediaExtractionUseCase` — работает с `source.video_path`, ему всё равно откуда путь
- `CleanupYoutubeVideoUseCase` — без изменений
- Track selection modal — UI тот же, только данные приходят иначе
- `FfmpegMediaExtractor`, `FfmpegSubtitleExtractor` — работают с путём, без изменений

## Миграция данных

Не требуется. Существующие source'ы с `video_path` указывающим на `data/videos/...` продолжат работать — файлы там уже лежат. Новые source'ы будут создаваться с оригинальными путями.
