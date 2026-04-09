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

Логи воркера смотрим **только через `make`** — общим потоком со всеми остальными сервисами (детали — `docs/running.md`):

```
make dev-logs     # app + worker + redis + ai_proxy (dev)
make prod-logs    # app + worker + redis + ai_proxy (prod)
```

Перезапуск воркера (в обход пересборки всего compose):

```
docker compose -p anything-anki-dev restart worker    # dev
docker compose -p anything-anki-prod restart worker   # prod
```

Если когда-нибудь понадобится смотреть логи только воркера — это повод **добавить `make`-таргет**, а не обращаться к `docker compose logs` напрямую из кода/инструкций. Все логи должны быть доступны через `make`.
