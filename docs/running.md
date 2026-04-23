# Запуск

Проект клонирован в две независимые рабочие копии: `anything-to-anki/` (dev) и `anything-to-anki-prod/` (prod). В каждой — одинаковый набор команд, поведение различается через локальный `.env`.

## Характеристики копий

| | dev | prod |
|---|---|---|
| Web порт | `17832` | `17833` |
| ai_proxy порт | `8766` | `8767` |
| БД | `./data/app.db` (в dev-папке) | `./data/app.db` (в prod-папке) |
| `INSTANCE_ENV_NAME` | `dev` | `prod` |
| Docker project | `anything-anki-dev` | `anything-anki-prod` |
| URL | http://localhost:17832 | http://localhost:17833 |

Значения задаются в `./.env` каждой копии. Шаблон — `.env.example` (коммитится в git). При первом запуске в новой копии: `cp .env.example .env` и при необходимости отредактировать (в prod-копии — поменять значения на prod-шные).

## Команды (в каждой копии)

```
make up           # Поднять (ai_proxy на хосте + docker compose в фоне)
make down         # Остановить
make logs         # Все логи: app + worker + redis + ai_proxy одним потоком

make test         # Запустить backend-тесты
make lint         # ruff
make typecheck    # mypy
make help         # Все команды с описанием
```

## Словари

Проект использует словарные данные (CEFR, аудио, IPA, usage) в unified JSON формате. Подробности формата — в `dictionaries/README.md`.

**Первоначальная настройка:**

1. Подготовьте словари в unified JSON формате (см. `dictionaries/README.md`). Для генерации из открытых источников — [anything-to-anki-parsers](https://github.com/kudrmax/anything-to-anki-parsers)
2. Укажите путь к папке с unified JSON через `DICTIONARIES_DIR` в `.env`
3. `make up` автоматически соберёт SQLite-кэш из JSON

**Без `DICTIONARIES_DIR`** проект запустится, но CEFR-классификация будет использовать только встроенный fallback (cefrpy), а аудио/IPA/usage будут пустыми.

## Ключевые env vars (в `.env`)

- `INSTANCE_ENV_NAME` — визуальный лейбл копии. Отображается в UI бейджем. **Не** переключатель логики.
- `PORT` — порт web-приложения на localhost.
- `AI_PROXY_PORT` — порт ai_proxy на хосте.
- `COMPOSE_PROJECT_NAME` — имя docker compose проекта (обязано отличаться между копиями).
- `DICTIONARIES_DIR` — путь к папке с unified-словарями (по умолчанию: `dictionaries/` в корне проекта).
- `LOCAL_VIDEO_DIR` — (опционально) папка с локальными видеофайлами. Маунтится в контейнер readonly. Нужна только для добавления локальных видео через вкладку File.

В контейнер также пробрасываются:
- `DATA_DIR=/data` — путь к данным внутри контейнера (задаётся в `Dockerfile`, трогать не нужно).
- `AI_PROXY_URL`, `ANKI_URL`, `PROMPTS_CONFIG_PATH` — задаются в `docker-compose.yml`.

## Обновление prod до новой версии

1. Закоммитить работу в dev-копии (и запушить, если есть remote).
2. Перейти в prod-копию:
   ```bash
   cd ~/PycharmProjects/anything-to-anki-prod
   git pull origin master
   make down && make up
   ```

Данные в `./data/` не трогаются — git их игнорирует. Alembic миграции отработают автоматически при старте.

## Откат prod

```bash
cd ~/PycharmProjects/anything-to-anki-prod
git log --oneline -10       # найти предыдущий рабочий коммит
git checkout <sha>
make down && make up
```

⚠ Откат НЕ откатывает Alembic-миграции. Если обновление включало миграцию, после отката нужно вручную решить, что делать со схемой. Политика: не выкатывать миграции вместе с непроверенным кодом.

## Создание prod-копии (один раз)

```bash
cd ~/PycharmProjects
git clone anything-to-anki anything-to-anki-prod
cd anything-to-anki-prod
cp .env.example .env
# Отредактировать .env:
#   INSTANCE_ENV_NAME=prod
#   PORT=17833
#   AI_PROXY_PORT=8767
#   COMPOSE_PROJECT_NAME=anything-anki-prod
make up
```

Remote у нового clone по умолчанию указывает на dev-папку через `file://`. Этого достаточно для solo-workflow. Если захочется GitHub: `git remote set-url origin git@github.com:…/anything-to-anki.git`.
