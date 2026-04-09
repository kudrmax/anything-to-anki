# Migrate `upgrade_schema` to Alembic

**Дата:** 2026-04-09
**Статус:** Spec → план реализации

## Контекст

В `backend/src/backend/infrastructure/persistence/database.py` живёт функция `upgrade_schema()` — параллельная Alembic-у система миграций с inline `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS`, обёрнутыми в `try/except: pass`. Вызывается из `lifespan` в `backend/src/backend/infrastructure/api/app.py` сразу после `run_alembic_migrations`. Это техдолг: `CLAUDE.md` декларирует «только Alembic», но код не соответствует. Цель — устранить параллельную систему, сохранить корректное состояние БД на dev и prod.

## Аудит текущего `upgrade_schema`

Из 13 операций функции 12 — мусор, 1 — реальная data migration:

| # | Операция | Состояние |
|---|---|---|
| 1 | `ALTER candidates ADD ai_meaning TEXT` | **Мёртвая колонка.** Не в моделях, не используется в коде |
| 2 | `ALTER sources ADD source_type` | **Дубль.** Колонка есть в `SourceModel`, на свежих БД создаётся `0001_initial_schema` |
| 3 | `ALTER candidates ADD is_phrasal_verb` | **Дубль** |
| 4 | `ALTER candidates ADD definition` | **Мёртвая колонка** |
| 5 | `ALTER sources ADD processing_stage` | **Дубль** |
| 6 | `ALTER sources ADD title` | **Дубль** |
| 7 | `CREATE TABLE generation_jobs` | **Зомби.** Дропнута в `0006_drop_legacy_job_tables`. `upgrade_schema` запускается ПОСЛЕ alembic, поэтому на каждом старте создаёт пустую таблицу обратно |
| 8 | `ALTER generation_jobs ADD candidate_ids_json` | **Зомби** |
| 9 | `ALTER generation_jobs ADD skipped_candidates` | **Зомби** |
| 10 | `ALTER sources ADD video_path` | **Дубль** |
| 11 | `ALTER sources ADD audio_track_index` | **Дубль** |
| 12 | `CREATE TABLE media_extraction_jobs` | **Зомби.** Дропнута в `0006` |
| 13 | `UPDATE settings ... rename anki_field_screenshot → anki_field_image` | **Единственная живая операция.** Data migration |

### Следствия для живых БД

На текущих dev и prod БД физически существуют:
- зомби-таблицы `generation_jobs`, `media_extraction_jobs` (пустые, никем не используются);
- осиротевшие колонки `candidates.ai_meaning`, `candidates.definition` (NULL, никем не используются).

Settings rename идемпотентен и почти наверняка уже отработал на обеих БД, но мы не полагаемся на это и сохраняем операцию в новой ревизии.

## Дизайн

### Архитектура

Одна новая Alembic-ревизия `0009_drop_upgrade_schema_legacy.py` (`down_revision="0008"`) делает всё идемпотентно через интроспекцию SQLite. После неё параллельная система удаляется из кода. Alembic становится единственным владельцем схемы — продуктовая цель достигнута.

### Содержимое ревизии 0009

**Хелперы** (как в `0006`/`0008`):
- `_table_exists(name)` через `sa.inspect(bind).get_table_names()`.
- `_column_exists(table, column)` через `sa.inspect(bind).get_columns(table)`.

**`upgrade()`** — последовательно:

1. **Settings data migration:**
   ```python
   bind.execute(text(
       "UPDATE settings SET key = 'anki_field_image' "
       "WHERE key = 'anki_field_screenshot' "
       "AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'anki_field_image')"
   ))
   bind.execute(text("DELETE FROM settings WHERE key = 'anki_field_screenshot'"))
   ```
   На свежих БД оба запроса — no-op.

2. **Drop zombie tables:**
   ```python
   if _table_exists("generation_jobs"):
       op.drop_table("generation_jobs")
   if _table_exists("media_extraction_jobs"):
       op.drop_table("media_extraction_jobs")
   ```

3. **Drop orphan columns** через `batch_alter_table` (SQLite требует table-rebuild для drop column):
   ```python
   orphan = [c for c in ("ai_meaning", "definition")
             if _column_exists("candidates", c)]
   if orphan:
       with op.batch_alter_table("candidates") as batch_op:
           for c in orphan:
               batch_op.drop_column(c)
   ```
   На свежей БД (где этих колонок никогда не было) — no-op.

**`downgrade()`:** no-op с комментарием. Восстанавливать мёртвые сущности бессмысленно, согласуется с подходом `0001`.

### Изменения в коде

**`backend/src/backend/infrastructure/persistence/database.py`:**
- Удалить функцию `upgrade_schema()` целиком.
- Удалить ставший неиспользуемым импорт `text` (если больше нигде в файле не нужен; `update` остаётся для `reset_stuck_processing`).

**`backend/src/backend/infrastructure/api/app.py`:**
- Убрать `upgrade_schema` из импорта.
- Удалить вызов `upgrade_schema(session_factory)` из `lifespan`.

### Порядок старта приложения после изменения

```
run_alembic_migrations(db_url)   # включая новую 0009
reset_stuck_processing(...)
reconcile_media_files(...)
```

Никаких прямых DDL в Python-коде вне Alembic — соответствует `CLAUDE.md`.

## Pre-flight checks (обязательные перед применением)

1. **Grep по коду** на отсутствие использований мёртвых сущностей:
   - `ai_meaning`, `definition` в `backend/src/`, `frontends/`, тестах.
   - `generation_jobs`, `media_extraction_jobs` (как имена таблиц/моделей) в `backend/src/`.
   - Ожидаемый результат: упоминаются только в `database.py` (старый `upgrade_schema`) и в alembic-ревизиях `0006`/`0009`.
   - **Если найдены реальные использования** — стоп, эскалация пользователю до любых изменений.

2. **Поиск тестов на `upgrade_schema`:** `Grep "upgrade_schema"` по `backend/tests/`. Если есть — переделать или удалить.

3. **Проверить foreign keys и индексы на `candidates`** через `sqlite3 data/app_dev.db "PRAGMA foreign_key_list(candidates); PRAGMA index_list(candidates);"`. `batch_alter_table` копирует их по умолчанию, но мы должны знать что копируется, чтобы потом сравнить.

## Verification

1. **Lint + typecheck:** `make lint && make typecheck` для модифицированных файлов.
2. **Юнит-тесты:** `make test` целиком.
3. **Smoke на свежей БД:** временный пустой sqlite, прогнать `alembic upgrade head` → проверить, что в схеме нет `generation_jobs`, `media_extraction_jobs`, нет колонок `ai_meaning`, `definition`, ключа `anki_field_screenshot`.
4. **Dev окружение:**
   - `make dev-down && make dev-up`.
   - `make dev-logs` — alembic должен применить `0009`.
   - `sqlite3 data/app_dev.db ".tables"` — нет зомби-таблиц.
   - `sqlite3 data/app_dev.db ".schema candidates"` — нет осиротевших колонок.
   - Открыть UI, проверить что источники/кандидаты/настройки на месте.
5. **Prod окружение** — только после успешного dev:
   - **Бэкап:** `cp data/app_prod.db data/app_prod.db.bak-2026-04-09`. Без бэкапа prod не трогать.
   - `make prod-down && make prod-up`.
   - `make prod-logs` — alembic применил `0009`, ошибок нет.
   - Те же проверки схемы, что и для dev, но против `app_prod.db`.
   - Smoke в prod UI: источники, кандидаты, настройки видны и корректны.

## Rollback

- Если миграция упадёт на dev — баг в коде ревизии, фиксим, повторяем на dev.
- Если миграция упадёт на prod — `make prod-down`, `cp data/app_prod.db.bak-2026-04-09 data/app_prod.db`, разбираемся.
- Если миграция прошла, но проявился функциональный регресс — то же самое: остановить prod, восстановить из бэкапа, разбираться.

## Риски

- **`batch_alter_table` пересоздаёт `candidates`.** Это безопасная alembic-операция, но она физически копирует все строки. На большой таблице может быть заметно по времени, на текущих объёмах — мгновенно. Бэкап prod БД обязателен (см. Verification).
- **`ai_meaning`/`definition` могут содержать данные, о которых мы не знаем.** Митигация — pre-flight grep. Если ничто в коде эти колонки не пишет, данных там нет (или они мусор) — дроп безопасен.
- **Settings rename data migration** идемпотентна и безопасна повторно: `WHERE NOT EXISTS` защищает от конфликта первичного ключа.

## Что НЕ входит в задачу

- Чистка остального техдолга в `database.py` (например, `reconcile_media_files` и его safety guard).
- Изоляция dev/prod данных через отдельные `MEDIA_ROOT`/`DATA_DIR` (это отдельная закрытая задача в `Done`).
- Изменение моделей или поведения приложения. Только удаление параллельной системы миграций.
