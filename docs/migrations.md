# Миграции БД

Единственный способ менять схему БД — **Alembic**. Никаких inline-`ALTER TABLE` / `CREATE TABLE` в Python-коде. Миграции живут в `backend/src/backend/alembic/versions/` и применяются автоматически при старте контейнера через `run_alembic_migrations()` в lifespan-хуке FastAPI.

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
- При старте контейнера `run_alembic_migrations()` автоматически дотягивает БД до `head` — никаких ручных `alembic upgrade` на prod не нужно
