# Миграции БД

Единственный способ менять схему БД — **Alembic**. Никаких inline-`ALTER TABLE` / `CREATE TABLE` в Python-коде. Миграции живут в `backend/src/backend/alembic/versions/` и применяются автоматически при старте приложения через `run_alembic_migrations()` в lifespan-хуке FastAPI.

## Как добавить миграцию

```bash
# 1. Сгенерировать ревизию (из активного venv с установленным backend)
cd backend
alembic -c alembic.ini revision --autogenerate -m "add foo column to candidates"

# 2. Проверить сгенерированный файл в backend/src/backend/alembic/versions/
#    — autogenerate не всегда улавливает всё, особенно переименования,
#    данные, check constraints. Всё, что не так, правим руками.

# 3. Протестить апгрейд локально
alembic -c alembic.ini upgrade head

# 4. Убедиться что downgrade работает
alembic -c alembic.ini downgrade -1
alembic -c alembic.ini upgrade head

# 5. Закоммитить файл ревизии вместе с изменениями моделей
```

## Правила

- Каждая ревизия должна быть **обратимой**: `downgrade()` обязателен. Если не получается откатить — документируй почему в docstring ревизии
- **Одна логическая миграция — одна ревизия.** Не миксовать несвязанные изменения
- **Данные мигрировать тоже через Alembic** — отдельной data-миграцией (см. `0004_migrate_candidate_enrichments_data.py` как пример)
- **Не переименовывать существующие ревизии** — линия истории важна, `alembic_version` в БД ссылается на конкретные id
- При старте приложения `run_alembic_migrations()` автоматически дотягивает БД до `head` — никаких ручных `alembic upgrade` на prod не нужно

## Миграция 0049: слова и фразы

`0049_words_and_phrases` сливает карточки в слова (`candidates`, одно на лемму источника) и фразы (`phrases`), переносит результаты генерации, задачи и `anki_synced_cards` на `phrase_id`, убирает `enrichment_cache`.

- Перед миграцией `DatabaseBackup` копирует БД в `data/backups/app-<UTC>.db`; хранятся последние 5 (`BACKUPS_KEPT`), старые уходят в `backups/.trash/`, не удаляются.
- Миграция **односторонняя**: откат данных невозможен, вернуться можно только из копии.
- Есть opt-in тест на копии prod-БД (только чтение, миграция идёт на копии во временной папке): `MIGRATION_PROD_COPY=1 DICTIONARIES_DIR=... .venv/bin/python -m pytest backend/tests/integration/test_migration_0049_on_prod_copy.py -q -s`. Пока не запускался. БД должна быть на ревизии 0048.
