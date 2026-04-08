# Background Definition Generation Pipeline

**Date:** 2026-04-06
**Status:** Draft

## Problem

1. Ревью кандидатов без определений затруднено — пользователю приходится генерировать meaning вручную по клику
2. Free Dictionary API ненадёжен, ограничен и не даёт контекстные определения
3. Генерация всех определений за раз слишком долгая и дорогая (300 слов на серию)
4. Два поля (`ai_meaning` + `definition`) создают путаницу — на деле нужно одно `meaning`

## Solution

Заменить Dictionary API на фоновую генерацию через Claude с персистентной очередью в БД. Определения генерируются батчами (10-20 слов за запрос) через structured output. Пользователь запускает/останавливает генерацию, определения появляются постепенно во время review через polling.

## Design

### Data Model Changes

**StoredCandidate:**
- Убрать: `ai_meaning`, `definition`
- Добавить: `meaning: str | None` (заполняется Claude)
- Оставить: `ipa: str | None` (теперь тоже заполняется Claude)

**Новая сущность — GenerationJob:**
- `id: int`
- `source_id: int | None` — None означает "все source'ы"
- `status: GenerationJobStatus` (PENDING, RUNNING, PAUSED, COMPLETED, FAILED)
- `total_candidates: int`
- `processed_candidates: int`
- `failed_candidates: int`
- `created_at: datetime`

### Удаление Dictionary API

Полностью удаляются:
- `DictionaryEntry` entity
- `DictionaryProvider` port
- `CachedDictionaryApiProvider` adapter
- Dictionary cache (таблица/репозиторий)
- `ProcessingStage.FETCHING_DEFINITIONS`
- Настройка `enable_definitions`
- Эндпоинт `POST /sources/{id}/generate-all-meanings`

### Pipeline Changes

**Processing pipeline** (ProcessSourceUseCase):
- Stage 1: CLEANING_SOURCE (без изменений)
- Stage 2: ANALYZING_TEXT (без изменений)
- ~~Stage 3: FETCHING_DEFINITIONS~~ (удалён)
- Кандидаты создаются с `meaning=None`, `ipa=None`

**Background generation** (новый):
- Worker берёт job из БД
- Для каждого батча: выбирает N кандидатов где `meaning IS NULL`
- Приоритет: `is_sweet_spot DESC, cefr_level DESC`
- Формирует prompt с контекстом всех слов батча
- Вызывает Claude со structured output → получает meaning + IPA для каждого
- Сохраняет результаты, обновляет прогресс job'а
- Между батчами проверяет: не поставлен ли job на паузу

### Structured Output (single + batch)

Оба режима (on-demand по клику и batch в фоне) переходят на structured output через `output_format` в `ClaudeAgentOptions`. Единый промпт-шаблон (`generate_meaning`), IPA генерируется всегда.

**Single (on-demand):**
```json
{
  "type": "object",
  "properties": {
    "meaning": {"type": "string"},
    "ipa": {"type": "string"}
  },
  "required": ["meaning", "ipa"]
}
```

**Batch (background):**
```json
{
  "type": "object",
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "lemma": {"type": "string"},
          "pos": {"type": "string"},
          "meaning": {"type": "string"},
          "ipa": {"type": "string"}
        },
        "required": ["lemma", "pos", "meaning", "ipa"]
      }
    }
  },
  "required": ["results"]
}
```

System prompt — из существующего промпт-шаблона (`generate_meaning`). Промпт обновляется: убираются инструкции про формат строк (structured output сам определяет формат), фокус на содержание meaning.

User prompt (single) — как сейчас: `Word: "{lemma}" ({pos})\nContext: "{context}"`

User prompt (batch) формируется из списка кандидатов:
```
Word 1: "elaborate" (VERB)
Context: "She elaborated on the plan during the meeting."

Word 2: "reluctant" (ADJ)
Context: "He was reluctant to leave the party."
```

Результаты батча матчатся обратно по `(lemma, pos)`.

### Worker Lifecycle

1. **Start:** `POST /generation/start {source_id?: int}` → создаёт `GenerationJob(PENDING)` → запускает asyncio task
2. **Run:** Worker ставит `RUNNING`, цикл батчей, коммит после каждого
3. **Stop:** `POST /generation/{id}/stop` → ставит `PAUSED` в БД → worker видит на следующей итерации и останавливается
4. **Complete:** Когда не осталось кандидатов без meaning → `COMPLETED`
5. **Restart recovery:** При старте сервера `RUNNING` → `PENDING`, затем автоматический запуск pending jobs

### API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/generation/start` | Создать job и запустить (202) |
| POST | `/generation/{job_id}/stop` | Остановить после текущего батча |
| GET | `/generation/status` | Текущий статус (для polling) |

Сохраняется: `POST /candidates/{id}/generate-meaning` — on-demand генерация для одного кандидата.

### Frontend

- **InboxPage:** глобальная кнопка start/stop генерации + прогресс
- **SourceCard:** кнопка "сгенерировать определения" для конкретного source
- **ReviewPage:** polling каждые 10 сек, определения появляются постепенно, прогресс-бар, кнопка Stop
- **CandidateCardV2:** `candidate.meaning` вместо `ai_meaning || definition`
- Убрать `fetching_definitions` из processing stages

### DB Migration

SQLite не поддерживает DROP COLUMN надёжно. Стратегия:
1. `ALTER TABLE candidates ADD COLUMN meaning TEXT`
2. `UPDATE candidates SET meaning = COALESCE(ai_meaning, definition) WHERE meaning IS NULL`
3. `ai_meaning` и `definition` остаются в таблице как мёртвые колонки (не читаются и не пишутся)
4. `CREATE TABLE IF NOT EXISTS generation_jobs (...)`

### Error Handling

- Если батч падает → `failed_candidates += batch_size`, переход к следующему батчу
- Если весь worker крашится → job остаётся `RUNNING` → при рестарте сбрасывается в `PENDING`
- Ограничение: одновременно только один RUNNING/PENDING job

### Prompt Update

Текущий дефолтный промпт описывает 4-строчный текстовый формат (LINE 1-4). При переходе на structured output формат ответа определяется JSON schema, а не текстовой инструкцией. Промпт обновляется:
- Убрать инструкции про LINE 1-4 формат
- Оставить инструкции по содержанию: контекстное определение, русский перевод, синонимы
- IPA генерируется через schema-поле, не нужна инструкция в промпте
- Промпт-шаблон в БД обновляется через `upgrade_schema()` (INSERT OR REPLACE)

### What Stays

- On-demand `POST /candidates/{id}/generate-meaning` — генерация по клику (теперь тоже structured output, возвращает meaning + ipa)
- Prompt template system — настройка промпта через UI
- Existing prompt key (`generate_meaning`) — используется и для батча, и для on-demand
