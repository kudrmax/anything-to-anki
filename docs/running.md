# Dev/Prod флоу

Инструмент запускается **только локально**. В проекте два полностью независимых окружения — `dev` и `prod`, каждое со своей БД, портом и экземпляром `ai_proxy`.

## Характеристики окружений

| | dev | prod |
|---|---|---|
| Web порт | `17832` | `17833` |
| ai_proxy порт | `8766` | `8767` |
| БД | `data/app_dev.db` | `data/app_prod.db` |
| Docker project | `anything-anki-dev` | `anything-anki-prod` |
| `APP_ENV` | `development` (default) | `production` |
| URL | http://localhost:17832 | http://localhost:17833 |

## Основные команды

```
make dev-up         # Поднять dev (ai_proxy на хосте + контейнеры в фоне)
make dev-down       # Остановить dev
make dev-logs       # Логи контейнеров dev
make dev-logs-ai    # Логи ai_proxy dev

make prod-up        # Поднять prod
make prod-down      # Остановить prod
make prod-logs      # Логи контейнеров prod
make prod-logs-ai   # Логи ai_proxy prod

make help           # Все команды с описанием
```

## Ключевые env vars

Проставляются в docker-compose / Makefile, вручную обычно не нужны.

- `APP_ENV` — `development` или `production`. Определяет какая БД выбирается в `database.py`
- `DATA_DIR` — путь к данным (`/data` в контейнере, `.` локально)
- `AI_PROXY_URL` — адрес ai_proxy (`host.docker.internal:{8766|8767}`)
- `ANKI_URL` — адрес AnkiConnect (`host.docker.internal:8765`)
- `REDIS_URL` — `redis://redis:6379` внутри compose
- `PROMPTS_CONFIG_PATH` — путь к `prompts.yaml` внутри контейнера (`/app/config/prompts.yaml`)

## Прод-инцидент и защита

Был реальный data-loss инцидент: prod-контейнер поднялся без `APP_ENV=production`, выбрал dev-БД, и `reconcile_media_files` начал удалять prod-медиа, которых в dev-БД нет. Поэтому в коде стоит safety guard в `app.py` (отказ стартовать, если `APP_ENV=production`, но БД-URL содержит `app_dev.db`). **Эту проверку не трогать.**
