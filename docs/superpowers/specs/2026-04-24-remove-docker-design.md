# Уход от Docker — нативный запуск на macOS

## Мотивация

Docker слишком много жрёт RAM. Проект локальный, для одного пользователя — контейнерная изоляция не нужна. Все процессы запускаются нативно на хосте.

## Архитектура

Три процесса, запускаемые через `make up`:

1. **ai_proxy** — прокси к Claude API (уже работает на хосте)
2. **app** — FastAPI (uvicorn) + собранная статика фронтенда
3. **worker** — поллит SQLite-очередь, обрабатывает задачи (AI, media, pronunciation, video download)

TTS — отдельный subprocess, spawn'ится worker'ом по требованию. Загружает PyTorch/kokoro, обрабатывает все TTS-задачи из очереди, завершается. RAM полностью освобождается.

## `make setup` (одноразово)

Устанавливает всё, что нужно для работы:

- **brew-зависимости:** python@3.12, node, ffmpeg, espeak-ng
- **Python venv:** `.venv` с зависимостями из `backend/pyproject.toml`
- **Node modules:** `npm install` в `frontends/web/`

Один venv для всего (app, worker, ai_proxy) — убираем отдельный `.venv-ai-proxy`.

## `make up`

1. Проверяет что `make setup` был выполнен (venv существует, node_modules существуют, brew-зависимости установлены). Если нет — ошибка с сообщением `Run "make setup" first`.
2. Обновляет словарный кэш (`dict-update`)
3. Собирает фронтенд (`npm run build` в `frontends/web/`)
4. Запускает ai_proxy в фоне (PID-файл + лог)
5. Запускает app (uvicorn) в фоне (PID-файл + лог)
6. Запускает worker в фоне (PID-файл + лог)
7. Выводит баннер с URL

## `make down`

Убивает ai_proxy + app + worker по PID-файлам.

## `make logs`

Собирает логи всех трёх процессов в один поток (как сейчас).

## Worktree

`make up-worktree` — те же три процесса, но на портах `WORKTREE_PORT` / `WORKTREE_AI_PROXY_PORT`. Логика упрощается: вместо отдельного docker compose project — просто другие порты и PID-файлы.

## TTS subprocess

Worker при получении TTS-задачи spawn'ит `python -m backend.infrastructure.tts_worker`. Subprocess:

1. Загружает PyTorch + kokoro + модель
2. Поллит SQLite-очередь на TTS-задачи
3. Обрабатывает все найденные TTS-задачи
4. Когда очередь пуста — завершается
5. Процесс умер → вся RAM (PyTorch + модель) освобождена

Критерий завершения: после обработки очередного TTS-джоба проверяем очередь — если TTS-задач больше нет, subprocess завершается.

## Изменения в `.env`

**Удалить:**
- `COMPOSE_PROJECT_NAME` — docker-специфичное

**Оставить:**
- `PORT`, `AI_PROXY_PORT`, `INSTANCE_ENV_NAME`, `DICTIONARIES_DIR`, `LOCAL_VIDEO_DIR`
- `WORKTREE_PORT`, `WORKTREE_AI_PROXY_PORT`

## Изменения в Makefile

**Удалить:**
- Макрос `check_services` (docker-специфичный)
- Таргет `backfill-breakdowns` (использует `docker compose exec`)
- Все `docker compose` команды
- Отдельный `AI_VENV` (`.venv-ai-proxy`)

**Добавить:**
- `make setup` — одноразовая установка зависимостей
- Защита в `make up`: не работает если `make setup` не выполнен
- Сборка фронтенда в `make up`
- Запуск app и worker как фоновых процессов с PID-файлами

**Упростить:**
- `up-worktree` / `down-worktree` / `logs-worktree` — без docker compose, просто другие порты и PID-файлы

**Оставить как есть:**
- `test`, `coverage`, `test-ai`, `lint`, `typecheck` — уже нативные
- `dict-rebuild`, `dict-update` — уже нативные
- `_python_dev`, `_check_env`, баннер, `help`

## Что удалить из репозитория

- `Dockerfile`
- `Dockerfile.worker`
- `docker-compose.yml`

## Что остаётся без изменений

- Весь код backend (use cases, domain, persistence)
- Фронтенд (frontends/web/)
- ai_proxy.py
- SQLite-очередь (job_worker.py)
- Структура данных (./data/)
- Тесты
