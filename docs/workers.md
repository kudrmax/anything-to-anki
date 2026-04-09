# Воркеры и очереди

Асинхронная работа — **arq** (Redis-based job queue). Отдельный процесс в Docker-compose (`worker` сервис), тот же образ что и app.

## Где код

`backend/src/backend/infrastructure/workers.py` — job-функции и `WorkerSettings`.

## Текущие задачи

- `extract_media_for_candidate(candidate_id)` — вырезает скриншот и аудиофрагмент из видео для одного кандидата
- `generate_meanings_batch(candidate_ids)` — генерация значений, переводов, синонимов через AI, батчем до 15 кандидатов

## Параметры воркера

Retry, timeout, concurrency — в `WorkerSettings` в `workers.py`. Конкретные значения здесь намеренно не фиксируются, могут меняться при настройке под нагрузку.

## Принцип обработки задачи

Каждая задача сначала помечает свои объекты как `RUNNING` в отдельной commit'нутой сессии (чтобы прогресс был виден в UI даже при откате основной), затем выполняет use case. Permanent-ошибки (`PermanentAIError`, `PermanentMediaError`) сразу ведут к `FAILED` без ретраев; на остальных — ретрай с финальной маркировкой `FAILED` на последней попытке. Детали реализации — в `workers.py`.

## Команды

```
docker compose -p anything-anki-dev logs -f worker    # Логи воркера dev
docker compose -p anything-anki-dev restart worker    # Перезапуск dev
docker compose -p anything-anki-prod logs -f worker   # Логи воркера prod
docker compose -p anything-anki-prod restart worker   # Перезапуск prod
```
