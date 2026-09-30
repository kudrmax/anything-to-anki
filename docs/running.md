# Запуск

Проект клонирован в две независимые рабочие копии: `anything-to-anki/` (dev) и `anything-to-anki-prod/` (prod). В каждой — одинаковый набор команд, поведение различается через локальный `.env`.

## Первоначальная установка

```bash
make setup    # Ставит brew-зависимости, Python venv, Node modules
```

Запускается один раз после клонирования. Ставит: python@3.12, node, ffmpeg, espeak-ng, создаёт `.venv`, устанавливает Python и Node зависимости.

Версии Python-пакетов зафиксированы в `requirements.lock`, поэтому dev и prod получают одинаковое окружение. Чтобы обновить зависимости: в dev-копии поставить новые версии в `.venv`, прогнать проверки, выполнить `make lock` и закоммитить `requirements.lock`; в prod после `git pull` выполнить `make setup`.

## Характеристики копий

| | dev | prod |
|---|---|---|
| Web порт | `17832` | `17833` |
| ai_proxy порт | `8766` | `8767` |
| БД | `./data/app.db` (в dev-папке) | `./data/app.db` (в prod-папке) |
| `INSTANCE_ENV_NAME` | `dev` | `prod` |
| URL | http://localhost:17832 | http://localhost:17833 |

Значения задаются в `./.env` каждой копии. Шаблон — `.env.example` (коммитится в git). При первом запуске в новой копии: `cp .env.example .env` и при необходимости отредактировать (в prod-копии — поменять значения на prod-шные).

## Команды (в каждой копии)

```
make setup        # Установка зависимостей (версии — из requirements.lock)
make lock         # Зафиксировать версии Python-пакетов из текущего venv
make up           # Собрать фронтенд + запустить ai_proxy, app, worker
make down         # Остановить все процессы
make logs         # Все логи: app + worker + ai_proxy одним потоком

make test         # Запустить backend-тесты
make lint         # ruff
make typecheck    # mypy
make help         # Все команды с описанием
```

## Архитектура процессов

`make up` запускает три фоновых процесса:

1. **ai_proxy** — прокси к Claude API (на хосте, порт из `AI_PROXY_PORT`)
2. **app** — FastAPI (uvicorn) + собранная статика фронтенда (порт из `PORT`)
3. **worker** — поллит SQLite-очередь, обрабатывает фоновые задачи

TTS-задачи обрабатываются в отдельном subprocess, который spawn'ится worker'ом по требованию. После обработки всех TTS-задач subprocess завершается, освобождая RAM от PyTorch/kokoro.

## macOS-приложение

```bash
make app          # Собрать .app для этой копии и положить в ~/Applications
make test-macos   # Тесты оболочки
```

`make app` в prod-копии даёт «AnythingToAnki», в dev — «AnythingToAnki Dev»: у каждой копии своё приложение с путём к её папке и её `PORT` внутри. Нужны Xcode или Command Line Tools.

- При запуске: если сервер копии уже отвечает, приложение просто открывает его. Иначе выполняет `make up` в login shell (тот же `PATH`, что в терминале, поэтому находятся `npm` и `claude`) и ждёт сервер. Ошибку `make up` показывает в окне с кнопкой Retry.
- При выходе (Cmd+Q) выполняет `make down`, только если процессы запускало оно само. Cmd+W лишь прячет окно.
- На вкладке File кнопка «Choose…» открывает окно выбора Finder и подставляет полный путь. Файл не копируется: backend читает его по пути, как при ручном вводе.
- Файлы из Downloads, Desktop и Documents читают процессы, запущенные приложением, поэтому macOS спросит разрешение от имени приложения. Приложение подписано ad-hoc, так что после каждого `make app` разрешение может понадобиться дать заново.
- В worktree `make app` не работает: приложение запускает `make up`, а не `make up-worktree`.
- После `git pull` в копии пересобирать приложение не нужно, если не менялась папка `frontends/macos/`: интерфейс берётся с сервера.

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
- `DICTIONARIES_DIR` — путь к папке с unified-словарями.

## Обновление prod до новой версии

1. Закоммитить работу в dev-копии (и запушить, если есть remote).
2. Перейти в prod-копию:
   ```bash
   cd ~/projects/anything-to-anki-prod
   git pull origin master
   make down && make up
   ```

Данные в `./data/` не трогаются — git их игнорирует. Alembic миграции отработают автоматически при старте.

## Откат prod

```bash
cd ~/projects/anything-to-anki-prod
git log --oneline -10       # найти предыдущий рабочий коммит
git checkout <sha>
make down && make up
```

⚠ Откат НЕ откатывает Alembic-миграции. Если обновление включало миграцию, после отката нужно вручную решить, что делать со схемой. Политика: не выкатывать миграции вместе с непроверенным кодом.

## Перенос рабочей копии в другую папку

В `.venv` и в БД (пути к медиа) зашиты абсолютные пути, поэтому после переноса папки:

```bash
make down                    # до переноса
# ...перенести папку...
trash .venv && make setup    # окружение пересоздаётся с версиями из requirements.lock
make migrate-paths           # dry-run: сколько путей к медиа устарело
make migrate-paths APPLY=1
make up
```

Если переехала папка словарей — поправить `DICTIONARIES_DIR` в `.env` каждой копии.

## Создание prod-копии (один раз)

```bash
cd ~/projects
git clone anything-to-anki anything-to-anki-prod
cd anything-to-anki-prod
cp .env.example .env
# Отредактировать .env:
#   INSTANCE_ENV_NAME=prod
#   PORT=17833
#   AI_PROXY_PORT=8767
make setup
make up
```

Remote у нового clone по умолчанию указывает на dev-папку через `file://`. Этого достаточно для solo-workflow. Если захочется GitHub: `git remote set-url origin git@github.com:…/anything-to-anki.git`.
