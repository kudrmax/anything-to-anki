# TTS: озвучка предложений для текстовых источников (фаза 2)

## Проблема

Для VIDEO-источников аудио предложения извлекается из видеофайла (FFmpeg). Для TEXT и LYRICS источников аудио предложения нет — карточка Anki остаётся без аудио-компонента. TTS закрывает этот гэп, генерируя озвучку фразы синтезом речи.

## Решения

- **Провайдер: Kokoro** (82M параметров, офлайн, одна модель на все голоса)
- Генерация TTS-аудио для кандидатов текстовых источников (TEXT, LYRICS)
- Запуск только по кнопке (не автоматически)
- Кнопка на уровне источника — enqueue для всех кандидатов (аналогично media extraction и pronunciation)
- Если TTS-аудио уже есть — перезаписываем при повторном запуске
- Отдельное Anki-поле `AudioTTS` для экспорта
- Рандомный выбор голоса из включённых для каждого кандидата — разные фразы звучат разными голосами
- Модель грузится в RAM только на время генерации батча, после — выгружается

## Голоса и настройки

### Список голосов

Kokoro поддерживает 28 английских голосов (одна модель ~113MB, переключение между голосами — бесплатно по производительности):

**American English (20):**
- Female: `af_heart`, `af_alloy`, `af_aoede`, `af_bella`, `af_jessica`, `af_kore`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`
- Male: `am_adam`, `am_echo`, `am_eric`, `am_fenrir`, `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `am_santa`

**British English (8):**
- Female: `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`
- Male: `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`

### Управление голосами в Settings

Один список всех голосов с чекбоксами (вкл/выкл). По умолчанию — все включены. Пользователь отключает те, которые не нравятся.

Хранение в Settings (key-value store): ключ `tts_enabled_voices`, значение — JSON-список включённых voice ID. По умолчанию — все 28 голосов.

### Скорость

Настройка `tts_speed` в Settings: `float`, по умолчанию `1.0`. Применяется ко всем голосам одинаково.

### Рандомный выбор

При генерации TTS для кандидата — случайный выбор голоса из списка включённых (`random.choice`). Каждый кандидат получает свой голос. Выбранный голос не сохраняется в БД (инфраструктурная деталь).

## Управление памятью

Модель Kokoro (~700-800MB в RAM при работе) грузится **лениво** и **выгружается** после завершения батча:

1. Воркер получает TTS-джобу → адаптер проверяет, загружена ли модель
2. Если нет — загружает `KPipeline` в память (прогрев ~5-10s)
3. Генерирует аудио для кандидата
4. После завершения **всех** TTS-джоб в текущей очереди — выгружает модель из памяти (`del pipeline`, `gc.collect()`, `torch.cuda.empty_cache()` если GPU)
5. В idle-состоянии воркер не держит модель в RAM

Реализация: адаптер `KokoroTTSGenerator` хранит `_pipeline: KPipeline | None`, загружает при первом вызове `generate_audio()`. Воркер после обработки последней TTS-джобы вызывает метод `unload()` адаптера.

## Модель данных

Новая таблица `candidate_tts` (Alembic-миграция):

| Колонка | Тип | Описание |
|---------|-----|----------|
| `candidate_id` | `int` PK, FK → `word_candidates.id` | 1:1 с кандидатом |
| `audio_path` | `str \| None` | Путь к аудиофайлу |
| `generated_at` | `datetime \| None` | Время генерации |

Файлы: `{media_root}/{source_id}/{candidate_id}_tts.m4a`

Доменная сущность: `CandidateTTS` (frozen dataclass).

## Архитектура (по слоям)

### Domain

- **Entity** `CandidateTTS` — frozen dataclass в `domain/entities/`
- **Port** `CandidateTTSRepository` (ABC) — `upsert()`, `get_by_candidate_id()`, `get_eligible_candidate_ids(source_id)`
- **Port** `TTSGenerator` (ABC) — `generate_audio(text: str, out_path: Path, voice: str, speed: float) -> None`, `unload() -> None`

### Application

- **`GenerateTTSUseCase`** — генерирует TTS для одного кандидата:
  1. Загружает кандидата, берёт `sentence` текст
  2. Читает `tts_enabled_voices` и `tts_speed` из Settings
  3. Выбирает случайный голос из включённых
  4. Вызывает `TTSGenerator.generate_audio(sentence, out_path)` (голос и скорость передаются адаптеру)
  5. Вызывает `CandidateTTSRepository.upsert()` с путём и timestamp
  6. Если запись уже существует — перезаписывает файл и обновляет запись

- **`EnqueueTTSGenerationUseCase`** — находит всех кандидатов источника, создаёт `JobType.TTS` джобы. Аналогично `EnqueueMediaGenerationUseCase` и `EnqueuePronunciationDownloadUseCase`.

### Infrastructure

- **`SqlaCandidateTTSRepository`** — SQLAlchemy-реализация репозитория
- **`CandidateTTSModel`** — SQLAlchemy-модель таблицы
- **`KokoroTTSGenerator`** — реализация порта `TTSGenerator`:
  - `_pipeline: KPipeline | None` — ленивая загрузка
  - `generate_audio(text, out_path, voice, speed)` — генерация WAV → конвертация в M4A (AAC 96k mono через ffmpeg) → удаление WAV
  - `unload()` — выгрузка модели из RAM
- **`JobType.TTS`** — новый тип в enum
- **Обработчик в `job_worker.py`** — `_handle_tts()`, аналогично `_handle_pronunciation()`. После обработки последней TTS-джобы — вызов `unload()`
- **Alembic-миграция** — создание таблицы `candidate_tts`
- **DI в `container.py`** — wiring use cases и адаптеров

### Settings (новые ключи)

- `tts_enabled_voices` — JSON-список включённых voice ID. Default: все 28 голосов. Тип: `_JSON_LIST_KEYS`
- `tts_speed` — float, скорость речи. Default: `"1.0"`. Тип: `_FLOAT_KEYS` (новый тип, или хранить как строку и парсить)

### API

- `POST /api/sources/{id}/tts/enqueue` — запуск генерации TTS для всех кандидатов источника
- Прогресс — через существующий механизм джоб (UI опрашивает статус джоб)
- Settings API (`GET/PATCH /api/settings`) — без изменений, автоматически поддерживает новые ключи

### Frontend

- Кнопка «Generate TTS» на странице источника (только TEXT/LYRICS)
- Прогресс отображается через существующий job progress UI
- Страница Settings: секция «Text-to-Speech»
  - Список голосов с чекбоксами (все включены по умолчанию)
  - Слайдер или input для скорости (0.5–2.0, default 1.0)

### Экспорт в Anki

- Новое Anki-поле `AudioTTS` в настройках (`Settings`)
- В `sync_to_anki.py` — добавить логику: если `CandidateTTS.audio_path` существует, экспортировать как `[sound:filename]` в поле `AudioTTS`
- Обновить шаблон карточки Anki для отображения нового поля

## Что НЕ входит в скоуп

- Автоматическая генерация TTS при обработке источника
- TTS для VIDEO-источников
- Выбор конкретного голоса для конкретного кандидата (только рандом из включённых)
- Сохранение использованного голоса в БД
