# Карта проекта

```
anything-to-anki/
├── backend/                              # Python backend, Clean Architecture
├── frontends/web/                        # React 19 + Vite + TailwindCSS
├── ai_proxy.py                           # FastAPI-обёртка над claude-agent-sdk, на хосте
├── config/                               # Конфигурация (prompts.yaml и др.), read-only в контейнере
├── data/                                 # Docker volume (в .gitignore)
│   ├── app_prod.db / app_dev.db          # SQLite обоих окружений
│   ├── media/                            # Скриншоты и аудио из видео
│   └── redis/                            # Redis persistence
├── anki-templates/                       # Шаблоны карточек Anki
├── docs/                                 # Спецификации, планы, справочная документация
├── Dockerfile / Dockerfile.worker        # app-образ и worker-образ
├── docker-compose.yml                    # Dev конфиг
├── docker-compose.prod.yml               # Prod overlay
└── Makefile                              # Все команды запуска и проверок
```

**Пояснения по компонентам:**

- **backend/** — вся бизнес-логика, трёхслойная Clean Architecture. Единственное место, где живут домен и use cases. Детали — `docs/architecture.md`.
- **frontends/web/** — чисто презентационный слой. Не содержит бизнес-логики (см. красный блок в CLAUDE.md).
- **ai_proxy.py** — отдельный процесс, запускается на хосте, не в Docker. Причины и устройство — `docs/ai-integration.md`.
- **config/** — конфигурация приложения (промпты для AI и прочее), монтируется в контейнер read-only.
- **data/** — единственное место, где живут пользовательские данные: БД обоих окружений, медиа, redis. Монтируется как volume в контейнер. На момент написания dev и prod **шерят** эту директорию (разные БД, общий `media/`) — архитектурный долг, запланирован фикс.

**Структура backend** (`backend/src/backend/`):

- `domain/` — entities, value_objects, ports, services, exceptions
- `application/` — use_cases, dto
- `infrastructure/` — adapters, api, persistence, workers, container

Подробная таблица слоёв — `docs/architecture.md`.
