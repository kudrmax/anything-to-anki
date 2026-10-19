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
| `infrastructure/queue/` | Очередь задач в SQLite и `JobWorker` (см. `docs/workers.md`) |
| `infrastructure/container.py` | **Единственное** место сборки зависимостей (DI) |

## Порты и адаптеры

- Все внешние зависимости (БД, AI, файлы, HTTP, Anki) скрыты за интерфейсами (ABC) в `domain/ports/`
- Реализации живут в `infrastructure/adapters/` или `infrastructure/persistence/`
- Use cases получают зависимости **только** через конструктор (constructor injection)
- Сборка графа зависимостей — **только** в `infrastructure/container.py`. Никаких прямых импортов `infrastructure` из use cases
- API-роуты тоже не создают use cases руками — берут готовые из DI-контейнера

## Слова и фразы

Доменная модель источника (спека — `docs/specs/words-phrases-rebuild.md`):

- **Слово** (`Word`, таблица `candidates`) — одна лемма источника `(source_id, lower(lemma), is_phrasal_verb)`: CEFR, частотность, произношение, картинка и статус решения (`candidates.status`, `DecisionStatus`: pending / learn / learning / known).
- **Фраза** (таблица `phrases`) — вхождение слова в текст со всем, что к нему относится: текст, Polish, определение, озвучка, клип, cloze, граница. Поля: `origin` (`auto` / `manual` / `example` / `collected`), `shown_by` (`selection` | `user` | NULL), `choice` (`CardChoice`: none / learn / cloze / known / skip), `revision`, `replaces_selection`.
- **Карточка** на экране = одна показанная фраза (`shown_by` не NULL). Ключ карточки в API и во фронте — `phrase_id`.
- **Решение — выбор на одной карточке слова**, его карточке решения (`choice` learn, cloze или known); она уходит в Anki. Остальные карточки решённого слова только показывают решение. **Skip** — выбор одной фразы, слово не меняется.
- Что делает нажатие, перенос, экспорт и снятие Known, решают таблицы `domain/services/decision_rules.py`; что видит карточка — `card_view.py`. Модель статусов — `docs/specs/words-phrases-rebuild.md`.
- Какие фразы показывать, решает чистая функция `select_phrases` (`domain/services/phrase_selection.py`); защита от потерь — `phrase_protection.py` (`is_touched`), план пересборки — `rebuild_plan.py`.

### Lossless Rebuild

Вместо Reprocess — `RebuildSource(source_id, include_open)` и `PreviewRebuild`. Анализ идёт в фоне вне транзакции, затем план (`plan_rebuild`) применяется в одной write-транзакции `BEGIN IMMEDIATE` (`SQLITE_BUSY_TIMEOUT_MS` = 30 с). `auto`-фразы upsert'ятся по ключу вхождения, id стабильны; решения, генерация и тронутые фразы не теряются. `include_open` позволяет перенести показанную фразу и с карточек со сгенерированным. Темы пересобирать нельзя: `RefreshTopic` только добавляет. Какая операция доступна источнику, решает backend (`available_operation`).

Длинные операции (обработка, Rebuild, Preview) берут замок в таблице `source_operations`; вторая операция над тем же источником получает 409, в том числе ручные задачи генерации во время Rebuild.

### Кэш разбора

`CachingDocumentAnalyzer` (декоратор над анализатором) хранит разбор spaCy в `document_parses`, ключ `(document_hash, analyzer_version)`. Повторный анализ того же текста не разбирает его заново.

### Learning и таймер

- Экспорт привязывает карточку к заметке Anki: строка `anki_synced_cards` (лемма, вид заметки, `learning_since`, `released_at`), слово становится Learning. Приложение никогда не спрашивает Anki о прогрессе.
- Learning читается как Known через 30 дней после экспорта (`LEARNING_KNOWN_AFTER_DAYS`); это вычисляется при чтении, ничего не переключается. Приоритет Unknown > Known > Learning > Learn. Слово Learning или Learn в других источниках не предлагается как новое, но во фразах считается незнакомым.
- Снять Known любым способом (кнопкой, в Settings, через Unknown) значит сделать слово новым во всех источниках: привязки отпускаются, заметки остаются в Anki. Удалённый источник оставляет привязки своих карточек Learn и Cloze: слово остаётся Learning до таймера.
