# Карта проекта

```
anything-to-anki/
├── backend/                              # Python backend, Clean Architecture
├── frontends/web/                        # React 19 + Vite, CSS-модули на токенах (src/styles/tokens.css)
├── ai_proxy.py                           # FastAPI-обёртка над claude-agent-sdk, отдельный процесс
├── config/                               # Конфигурация (prompts.yaml и др.)
├── data/                                 # Данные этой рабочей копии (в .gitignore)
│   ├── app.db                            # SQLite: данные приложения и очередь job'ов
│   ├── media/                            # Скриншоты и аудио из видео
│   └── videos/                           # Скачанные видео
├── .venv/                                # Python-окружение копии (в .gitignore), создаёт make setup
├── .logs/ и .pids/                       # Логи и PID-файлы запущенных процессов (в .gitignore)
├── anki-templates/                       # Шаблоны карточек Anki
├── docs/                                 # Спецификации, планы, справочная документация
├── .env.example                          # Шаблон локального .env для рабочей копии
└── Makefile                              # Все команды запуска и проверок
```

**Пояснения по компонентам:**

- **backend/** — вся бизнес-логика, трёхслойная Clean Architecture. Единственное место, где живут домен и use cases. Детали — `docs/architecture.md`.
- **frontends/web/** — чисто презентационный слой. Не содержит бизнес-логики (см. красный блок в CLAUDE.md).
- **ai_proxy.py** — отдельный процесс рядом с app и worker. Причины и устройство — `docs/ai-integration.md`.
- **config/** — конфигурация приложения (промпты для AI и прочее). Приложение её только читает.
- **data/** — единственное место, где живут пользовательские данные этой копии: БД, медиа, видео. У dev- и prod-копии она своя, общего состояния между копиями нет.
- **Словари** лежат вне репозитория: путь к ним задаётся `DICTIONARIES_DIR` в `.env`, кэш собирается в `$DICTIONARIES_DIR/.cache/dict.db` командой `make dict-update`.

Все процессы (app, worker, ai_proxy) запускаются нативно из `.venv` через `make up` — Docker в проекте не используется.

**Структура backend** (`backend/src/backend/`):

- `domain/` — entities, value_objects, ports, services, exceptions
- `application/` — use_cases, dto
- `infrastructure/` — adapters, api, persistence, queue, services, config, container

Подробная таблица слоёв — `docs/architecture.md`.
