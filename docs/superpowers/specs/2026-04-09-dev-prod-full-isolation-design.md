# Полная изоляция dev и prod через физически независимые рабочие копии

**Дата:** 2026-04-09
**Статус:** Design, ожидает реализации

---

## 1. Цель

Сделать так, чтобы **ни при каких условиях** dev-процесс не мог повредить prod-данные (и наоборот). Убрать все защитные костыли, которые компенсируют неудачный базовый паттерн.

## 2. Проблема

Текущая схема: **одно дерево проекта, два окружения внутри него, выбираются через env var**. Dev и prod живут в одной рабочей папке, различаются только именем БД (`app_dev.db` vs `app_prod.db`) и значением `APP_ENV`. Всё остальное — медиа, redis dump, config, код, git-состояние — общее.

Это стандартный паттерн для командной разработки (dev/staging/prod на разных серверах, выбираются через окружение). Для **локального приложения на одной машине** он создаёт фундаментальную уязвимость: любой логический switch — env var, имя файла, флаг — является точкой отказа. Один забытый `APP_ENV=production` → data loss.

В июне 2026 это уже один раз случилось: prod-контейнер пересобрался без `APP_ENV=production`, code по умолчанию выбрал dev-БД, `reconcile_media_files` при старте увидел много медиа-директорий, которых «нет в БД» (потому что БД была не та), и `rmtree`-ом снёс prod-медиа. Текущие защиты — startup guard в `app.py` и счётчик в `reconcile_media_files` — это ответ на симптом, а не на причину.

Причина: **логическая изоляция вместо физической**.

## 3. Принцип

Изоляция должна быть физической. Процесс, обслуживающий dev, должен быть технически не в состоянии увидеть prod-файлы. Не «может, но проверяет env var» — а не может в принципе, потому что они лежат в другой папке, которая для этого процесса вне его working directory.

Практическое воплощение: **две независимые рабочие копии (git clone'а) проекта**. Каждая имеет свою `./data/`, свой `./.env`, запускается своими командами из своей директории. Код **не знает** про dev/prod, он всегда работает с `./data/app.db`.

## 4. Целевая архитектура

### Раскладка на диске

```
~/PycharmProjects/anything-to-anki/          ← dev-копия (существующая)
  .env                    ← локально, .gitignored
  .env.example            ← в git
  .git/
  data/                   ← dev-данные, .gitignored
    app.db
    media/
    redis/
  backend/ frontends/ docker-compose.yml ...

~/PycharmProjects/anything-to-anki-prod/     ← prod-копия (новая)
  .env                    ← локально, .gitignored
  .env.example            ← в git
  .git/
  data/                   ← prod-данные, .gitignored
    app.db
    media/
    redis/
  backend/ frontends/ docker-compose.yml ...
```

Обе копии — **полные git clone'ы** с независимыми `.git` директориями. Prod-копия — это второй clone, который обновляется через `git pull` из remote (или напрямую из dev-копии, см. секцию 9).

### Workflow

| Действие | Где |
|---|---|
| Писать код, коммитить, ветки | dev-копия |
| Пользоваться продуктом (реальное изучение английского) | prod-копия |
| Запускать для экспериментов/тестов | dev-копия, `make up` |
| Обновлять prod до новой версии | `cd prod && git pull && make down && make up` |
| Откатить prod | `cd prod && git checkout <commit> && make down && make up` |

Prod-копия **не используется для редактирования кода**. В ней только `git`-операции (pull, checkout), `make down/up/logs` и доступ к `data/` при необходимости.

### Что физически невозможно после фикса

- dev-процесс увидеть prod-данные (они в другой физической папке, вне его CWD).
- prod-процесс загрузить dev-БД (выбора нет: код всегда открывает `./data/app.db`).
- `reconcile_media_files` снести чужие медиа (он видит только те, что лежат рядом с его БД).
- Забытый env var привести к data loss (env var больше не выбирает данные).

## 5. Изменения в backend-коде

### 5.1. `backend/src/backend/infrastructure/persistence/database.py`

**`default_db_url()`** сокращается до одной строки:

```python
def default_db_url() -> str:
    data_dir = os.getenv("DATA_DIR", ".")
    return f"sqlite:///{data_dir}/app.db"
```

Было: выбор `app_dev.db` / `app_prod.db` по `APP_ENV`. Станет: всегда `app.db`.

**`reconcile_media_files()`**:

- Удалить defensive guard (блок `_count_sources(session) < len(numeric_dirs)`, строки ~236–249).
- Удалить helper `_count_sources` — он использовался только в этом guard'е.
- Переписать docstring: убрать упоминания «wrong DB loaded», «APP_ENV misconfigured», «data-loss scenario». Оставить описание того, что функция делает: чистит orphan media-файлы/директории.

### 5.2. `backend/src/backend/infrastructure/api/app.py`

В `lifespan()` удалить блок defense-in-depth guard (строки ~43–54):

```python
# УДАЛИТЬ:
app_env = os.getenv("APP_ENV", "development")
if app_env == "production" and "app_dev.db" in db_url:
    raise RuntimeError(...)
```

Импорт `os` остаётся — он используется ниже для `os.environ.get("MEDIA_ROOT", ...)` и `os.getenv("DATA_DIR", ...)`.

### 5.3. Грепнуть на остатки

Перед коммитом: `grep -rn "APP_ENV\|app_dev.db\|app_prod.db" backend/src backend/tests ai_proxy.py Makefile Dockerfile* docker-compose*.yml` — не должно остаться ни одного совпадения. Исторические спеки в `docs/superpowers/specs/*` — это снапшоты во времени, их не трогаем.

## 6. Изменения во frontend-коде

### 6.1. `frontends/web/src/layouts/SidebarLayout.tsx` и `ClassicLayout.tsx`

**Условие отображения бейджа меняется:** сейчас бейдж показывается только если `VITE_APP_ENV !== 'production'` и хардкодит текст `dev`. Станет: бейдж показывается **всегда**, текст берётся из `VITE_INSTANCE_ENV_NAME`:

```tsx
{import.meta.env.VITE_INSTANCE_ENV_NAME && (
  <span style={{ ...те же стили... }}>
    {import.meta.env.VITE_INSTANCE_ENV_NAME}
  </span>
)}
```

**Почему всегда, а не только в dev:** если бейдж показывается только в одной из копий, это скрытая семантика «`prod` — особенное значение». Мы сознательно избегаем этого: `INSTANCE_ENV_NAME` — это только label, без логики. В dev-копии там будет `dev`, в prod-копии — `prod`, в обеих видно сразу, где ты находишься. Это именно то, что нужно для защиты от путаницы между двумя вкладками.

**Стили бейджа не меняются** — те же оранжевые, что и сейчас. Дизайн-дифференциация цветом не вводится намеренно (опять же — чтобы не появилась скрытая семантика).

Оба файла (`SidebarLayout.tsx`, `ClassicLayout.tsx`) правятся идентично.

### 6.2. `.env.example` для Vite

Vite читает переменные из `.env` в корне проекта автоматически. В `.env.example` (см. секцию 8) будет задокументировано, что `VITE_INSTANCE_ENV_NAME` должна присутствовать.

Важно: Vite bundle'ит эти переменные **на стадии build**. То есть значение `VITE_INSTANCE_ENV_NAME` фиксируется в момент `npm run build` (в нашем случае — в момент `docker compose build`). Менять его без пересборки frontend-а нельзя. В `docker-compose.yml` оно передаётся как build arg — см. секцию 7.

## 7. Изменения в инфраструктуре

### 7.1. `Dockerfile`

```diff
- ARG VITE_APP_ENV=development
- ENV VITE_APP_ENV=$VITE_APP_ENV
+ ARG VITE_INSTANCE_ENV_NAME
+ ENV VITE_INSTANCE_ENV_NAME=$VITE_INSTANCE_ENV_NAME
```

Убираем default value — теперь каждая копия обязана задать значение явно через `.env` (см. ниже). Если не задано — build упадёт, это sane default.

`ENV DATA_DIR=/data` остаётся без изменений.

### 7.2. `Dockerfile.worker`

Без изменений. `DATA_DIR=/data` остаётся. `APP_ENV` там и не читался.

### 7.3. `docker-compose.yml`

```yaml
services:
  app:
    build:
      context: .
      args:
        VITE_INSTANCE_ENV_NAME: ${INSTANCE_ENV_NAME}
    ports:
      - "${PORT}:8000"
    environment:
      ANKI_URL: http://host.docker.internal:8765
      AI_PROXY_URL: http://host.docker.internal:${AI_PROXY_PORT}
      REDIS_URL: redis://redis:6379
      PROMPTS_CONFIG_PATH: /app/config/prompts.yaml
    volumes:
      - ./data:/data
      - ./config:/app/config:ro
    depends_on:
      - redis

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      AI_PROXY_URL: http://host.docker.internal:${AI_PROXY_PORT}
      REDIS_URL: redis://redis:6379
      PROMPTS_CONFIG_PATH: /app/config/prompts.yaml
    volumes:
      - ./data:/data
      - ./config:/app/config:ro
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - ./data/redis:/data
```

Ключевые изменения:

- Удалена переменная `APP_ENV` из `environment` (она нигде больше не читается).
- `VITE_APP_ENV` → `VITE_INSTANCE_ENV_NAME` в build args.
- Убраны fallback-дефолты (`${PORT:-17832}`, `${APP_ENV:-development}` и т.п.). Если `.env` не задаёт переменную, compose упадёт с ошибкой. Это безопаснее, чем silent fallback: гарантирует, что обе копии не могут случайно съехать на одни и те же порты/имена.
- `COMPOSE_PROJECT_NAME` задаётся в `.env` (compose читает его автоматически, не нужно передавать в сервисы).

### 7.4. `docker-compose.prod.yml`

**Удалить файл.** Единственное, что он делал — хардкодил `APP_ENV=production`. После выпила `APP_ENV` файл становится пустым. В новой схеме нет различий в compose-конфигурации между копиями — обе используют один и тот же `docker-compose.yml`, различия задаются через `.env`.

### 7.5. `Makefile`

Текущий Makefile содержит парные таргеты `dev-up`/`prod-up`, `dev-down`/`prod-down`, `dev-logs`/`prod-logs` с захардкоженными константами `DEV_PORT=17832`, `PROD_PORT=17833` и т.д. После фикса вся эта двойная конструкция исчезает — каждая копия запускается своими одинаковыми командами, значения берутся из её `.env`.

Новый Makefile:

```makefile
.PHONY: up down logs test lint typecheck help _python_dev

# Читаем .env для Makefile-переменных (AI_PROXY_PORT).
# docker compose читает .env сам — это только для ai_proxy.
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

AI_VENV      := .venv-ai-proxy
AI_PID       := .pids/ai_proxy.pid
AI_LOG       := .logs/ai_proxy.log

define kill_ai_proxy_on_port
	@pid=$$(lsof -ti :$(1) 2>/dev/null); \
	if [ -n "$$pid" ] && ps -p $$pid -o args= 2>/dev/null | grep -q ai_proxy; then \
	    kill $$pid 2>/dev/null || true; \
	    echo "Killed ai_proxy on port $(1) (PID $$pid)"; \
	    sleep 0.5; \
	fi
endef

define start_ai_proxy
	@mkdir -p .pids .logs
	@[ -d $(AI_VENV) ] || (echo "Creating AI proxy venv..." && \
	    python3 -m venv $(AI_VENV) && \
	    $(AI_VENV)/bin/pip install -e ".[ai-proxy]")
	$(call kill_ai_proxy_on_port,$(AI_PROXY_PORT))
	@$(AI_VENV)/bin/python ai_proxy.py --port $(AI_PROXY_PORT) >> $(AI_LOG) 2>&1 & echo $$! > $(AI_PID); \
	    echo "AI proxy started on port $(AI_PROXY_PORT) (PID $$(cat $(AI_PID)))"
endef

define stop_ai_proxy
	$(call kill_ai_proxy_on_port,$(AI_PROXY_PORT))
	@rm -f $(AI_PID)
endef

_check_env:
	@if [ ! -f .env ]; then \
	    echo "ERROR: .env file missing. Copy .env.example to .env and fill in values."; \
	    exit 1; \
	fi

##@ Запуск (читает .env)
up: _check_env  ## Запустить (ai_proxy + docker compose)
	@echo "→ http://localhost:$(PORT)  (instance: $(INSTANCE_ENV_NAME))"
	$(call start_ai_proxy)
	docker compose up -d --build

down:  ## Остановить
	docker compose down
	$(call stop_ai_proxy)

logs:  ## Логи app + worker + redis + ai_proxy одним потоком
	@trap 'kill 0' INT TERM; \
	docker compose logs -f & \
	tail -F $(AI_LOG) 2>/dev/null | sed -l 's/^/ai_proxy        | /' & \
	wait

##@ Разработка
_python_dev:
	@[ -d .venv ] || python3 -m venv .venv
	@.venv/bin/pip install -e "backend/[dev]"

test: _python_dev
	.venv/bin/python -m pytest

lint: _python_dev
	.venv/bin/ruff check .

typecheck: _python_dev
	.venv/bin/mypy backend/src

##@ Прочее
help:
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	  /^[a-zA-Z_-]+:.*##/ { printf "  %-14s %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
```

Ключевые моменты:

- Единый набор команд `make up / down / logs`. Один и тот же Makefile в обеих копиях, ведёт себя по-разному только из-за `.env`.
- `include .env` подтягивает переменные в Makefile-пространство (`$(PORT)`, `$(AI_PROXY_PORT)` и т.д.).
- `_check_env` guard в `up` — если `.env` забыт, отказывается стартовать с понятным сообщением. Это важно: без `.env` compose попробует взять пустые значения и получится мусор.
- PID-файл ai_proxy упрощён до `ai_proxy.pid` (без суффиксов dev/prod) — в каждой копии свой `.pids/` (см. `.gitignore`).
- `docker compose -p <project>` убран — `COMPOSE_PROJECT_NAME` задаётся в `.env`, compose подхватит автоматически.

## 8. `.env` и `.env.example`

### 8.1. `.env.example` (коммитится в git)

```bash
# Визуальный лейбл этой копии — отображается в UI как бейдж рядом с логотипом
# и используется для имени docker compose проекта.
#
# ВАЖНО: это просто метка для человека. Код не принимает решений на основе
# этого значения. Не добавляйте сюда логику "если prod, то...". Для этого
# есть правильный способ (конфиг-файл, feature flag), но не этот переключатель.
INSTANCE_ENV_NAME=dev

# Порт веб-приложения на localhost. В prod-копии должен отличаться от dev,
# чтобы копии могли работать параллельно.
PORT=17832

# Порт ai_proxy на хосте. В prod-копии должен отличаться от dev.
AI_PROXY_PORT=8766

# Имя docker compose проекта. Должно отличаться между копиями, чтобы
# контейнеры не коллились. docker compose читает эту переменную автоматически.
COMPOSE_PROJECT_NAME=anything-anki-dev
```

### 8.2. `.env` для dev-копии

Содержимое идентично `.env.example` (значения уже настроены под dev). Первый шаг после миграции: `cp .env.example .env`.

### 8.3. `.env` для prod-копии

В новом clone'е `.env` создаётся вручную со значениями prod:

```bash
INSTANCE_ENV_NAME=prod
PORT=17833
AI_PROXY_PORT=8767
COMPOSE_PROJECT_NAME=anything-anki-prod
```

### 8.4. `.gitignore`

Добавить `.env` в `.gitignore` (если ещё нет). Текущий `.gitignore` уже игнорирует `data/`, `.pids/`, `.logs/`, `.venv*/` — это остаётся. Нужно добавить строку `.env`.

## 9. План миграции

Порядок шагов критичен — сначала остановить старое, потом удалять данные, потом менять код.

1. **Остановить все запущенные инстансы** (в текущей dev-копии, до любых изменений):
   ```bash
   make dev-down
   make prod-down
   ```

2. **Удалить все данные** (пользователь подтвердил: данные можно потерять, он их перегенерирует):
   ```bash
   rm -rf data/
   ```

3. **Применить изменения кода** (в dev-копии):
   - Правки в backend: `database.py`, `app.py`.
   - Правки во frontend: `SidebarLayout.tsx`, `ClassicLayout.tsx`.
   - Правки инфры: `Dockerfile`, `docker-compose.yml` (удалить fallback'и, переименовать build arg), удалить `docker-compose.prod.yml`, новый `Makefile`.
   - Новый `.env.example` в корне, `.env` в `.gitignore`.
   - Скопировать `.env.example` → `.env` (dev-значения).
   - Обновить документацию (см. секцию 11).
   - Грепнуть на остатки `APP_ENV`, `app_dev.db`, `app_prod.db`.
   - Запустить `make up`, проверить что работает, прогнать тесты (`make test`, `make lint`, `make typecheck`, `./node_modules/.bin/tsc -b` во frontend).
   - Коммит.

4. **Создать prod-копию**:
   ```bash
   cd ..
   git clone anything-to-anki anything-to-anki-prod
   cd anything-to-anki-prod
   ```
   Это создаст полный независимый clone. Origin у нового clone будет указывать на dev-папку как на `file://` remote — `git pull` из prod-копии будет тянуть из dev-папки напрямую, без нужды в GitHub. Это ок для solo-разработки.

   Если позже захочется использовать настоящий remote (GitHub): `cd prod && git remote set-url origin git@github.com:.../anything-to-anki.git`.

5. **Настроить prod-копию**:
   ```bash
   cd ~/PycharmProjects/anything-to-anki-prod
   cp .env.example .env
   # Отредактировать .env: INSTANCE_ENV_NAME=prod, PORT=17833, AI_PROXY_PORT=8767,
   # COMPOSE_PROJECT_NAME=anything-anki-prod
   ```

6. **Запустить prod-копию**:
   ```bash
   make up
   ```
   Alembic миграции отработают на пустой БД, создастся `./data/app.db`, `./data/media/`, redis. Приложение доступно на `http://localhost:17833` с бейджем `prod` в UI.

7. **Проверить параллельную работу**:
   - `cd ~/PycharmProjects/anything-to-anki && make up` — dev-копия должна подняться на `:17832`.
   - Обе вкладки открыты, оба бейджа видны, действия в одной не видны в другой.

8. **Обновить `TASKS.md`** — задача закрыта при предыдущем вызове `/next`, но ещё раз убедиться что запись в `Done` есть.

## 10. Регулярный workflow после миграции

### Обновление prod до новой версии кода

```bash
# 1. Работа сделана в dev-копии, коммит создан
cd ~/PycharmProjects/anything-to-anki
git commit -am "feat: ..."

# 2. Переключаемся в prod-копию и обновляем
cd ~/PycharmProjects/anything-to-anki-prod
git pull origin master         # тянет из dev-папки через file:// remote
make down && make up            # перезапуск с новым кодом
```

Alembic миграции отработают автоматически при старте приложения — но только на **prod**-БД в `./data/app.db`. Dev-БД никогда не затрагивается prod-копией.

### Откат prod

```bash
cd ~/PycharmProjects/anything-to-anki-prod
git log --oneline -10           # найти предыдущий рабочий коммит
git checkout <sha>
make down && make up
```

Данные в `./data/` не трогаются — git их игнорирует.

⚠ Откат НЕ откатывает Alembic-миграции. Если обновление включало миграцию, после отката нужно будет вручную решить, что делать со схемой: либо применить downgrade-ревизию (если написана), либо принять, что БД имеет новую схему, а код — старую (может привести к ошибкам). Это цена rollback'а; политика: не выкатывать миграции вместе с непроверенным кодом.

## 11. Обновления документации

### 11.1. `CLAUDE.md`

Секция **«Dev/Prod — главное правило»** переписывается:

- Удалить упоминания `app_dev.db` / `app_prod.db`, `APP_ENV`, safety guard в `app.py`.
- Удалить упоминание `make dev-up/down`, `make prod-up/down` — заменить на единое `make up/down/logs` в каждой копии.
- Вместо «Два независимых окружения dev и prod» — «Две независимые рабочие копии проекта».
- Переписать список «подводных камней» в низу файла: убрать пункты про APP_ENV, safety guard, shared `data/`.

Новый текст блока (набросок, уточнить при реализации):

> # КРИТИЧЕСКОЕ ПРАВИЛО: две рабочие копии, никакого общего состояния
>
> Проект клонирован в две независимые папки: `anything-to-anki/` (dev) и `anything-to-anki-prod/` (prod). У каждой — своя `./data/`, свой `./.env`, свои контейнеры. Код не знает про dev/prod, `INSTANCE_ENV_NAME` — только визуальный лейбл.
>
> - Разработка, эксперименты, ветки — **только в dev-копии**
> - Реальное использование продукта — **только в prod-копии**
> - Обновление prod: `cd prod && git pull && make down && make up`
> - Никаких правок кода в prod-копии — только `git`-операции и `make`
> - Никаких `cp data/... ../anything-to-anki-prod/data/...` между копиями

Секция про safety guard удаляется полностью (самого guard'а не будет).

### 11.2. `docs/running.md`

Полностью переписать: таблица с портами, команды, описание env vars.

Новый текст (набросок):

> # Запуск
>
> Проект клонирован в две независимые рабочие копии: `anything-to-anki/` (dev) и `anything-to-anki-prod/` (prod). В каждой — одинаковый набор команд, поведение различается через `.env`.
>
> ## Характеристики копий
>
> | | dev | prod |
> |---|---|---|
> | Web порт | `17832` | `17833` |
> | ai_proxy порт | `8766` | `8767` |
> | БД | `./data/app.db` (в dev-папке) | `./data/app.db` (в prod-папке) |
> | `INSTANCE_ENV_NAME` | `dev` | `prod` |
> | Docker project | `anything-anki-dev` | `anything-anki-prod` |
> | URL | http://localhost:17832 | http://localhost:17833 |
>
> Значения задаются в `./.env` каждой копии. Шаблон — `.env.example`.
>
> ## Команды (в каждой копии)
>
> ```
> make up         # Поднять (ai_proxy + docker compose)
> make down       # Остановить
> make logs       # Все логи: app + worker + redis + ai_proxy
> ```

### 11.3. `docs/architecture.md`, `docs/workers.md`, `docs/ai-integration.md`, `docs/migrations.md`, `docs/testing.md`, `docs/verify-before-done.md`

Проверить на упоминания `APP_ENV`, `app_dev.db`, `app_prod.db`, `make dev-*`, `make prod-*`, safety guard. Поправить или удалить.

### 11.4. `README.md` (если есть упоминания)

Аналогично.

## 12. Верификация

После применения изменений:

- **Backend:**
  - `make test` — все pytest зелёные. В тестах не должно остаться упоминаний `APP_ENV`.
  - `make typecheck` — mypy strict зелёный.
  - `make lint` — ruff зелёный (учитывая, что pre-existing 117 ошибок — отдельная задача, но новые ошибки не появились).
  - Приложение стартует, Alembic миграции проходят, реконсайл media работает.

- **Frontend:**
  - `cd frontends/web && ./node_modules/.bin/tsc -b` — без ошибок.
  - Бейдж `dev` виден в левом верхнем углу.

- **Параллельный запуск:**
  - `cd ~/PycharmProjects/anything-to-anki && make up` → приложение на `:17832`, бейдж `dev`.
  - `cd ~/PycharmProjects/anything-to-anki-prod && make up` → приложение на `:17833`, бейдж `prod`.
  - Обе копии работают одновременно, не конфликтуют по портам, по docker compose project name, по ai_proxy PID.
  - Создание источника в dev не приводит к появлению источника в prod.
  - Файл `data/app.db` существует **и** в dev-папке, **и** в prod-папке, это два разных файла.

- **Отсутствие legacy:**
  - `grep -rn "APP_ENV\|app_dev.db\|app_prod.db" .` — вообще никаких совпадений в actively supported файлах. (Исторические спеки в `docs/superpowers/specs/` можно не трогать — они отражают состояние на дату написания.)
  - `docker-compose.prod.yml` отсутствует.
  - В `Makefile` нет `dev-*` и `prod-*` таргетов.
  - В коде нет `_count_sources` и startup guard'а.

- **Документация:**
  - `CLAUDE.md`, `docs/running.md` описывают новый workflow.
  - `.env.example` в корне, `.env` в `.gitignore`.

## 13. Риски и митигации

| Риск | Митигация |
|---|---|
| Забыл создать `.env` в prod-копии → `make up` падает или берёт пустые значения | `_check_env` в Makefile отказывается стартовать без `.env`. Убраны `${VAR:-fallback}` в compose, чтобы не было silent fallback'а. |
| `COMPOSE_PROJECT_NAME` одинаковый в обеих копиях → контейнеры коллятся | В `.env.example` явно указано, что в prod-копии нужно поменять; заметно при первом запуске (compose ругнётся на существующие контейнеры). |
| Alembic миграция в новой версии кода несовместима с prod-БД, откат кода оставляет схему впереди кода | Явно задокументировано в секции «Откат prod». Политика: не выкатывать в prod непроверенные миграции. Отдельная задача (см. `TASKS.md`) — «Migrate upgrade_schema to Alembic» — не блокирует эту, но после её реализации ситуация станет чище. |
| Prod-копия «разошлась» с dev — забыл `git pull`, используешь старый код | Prod обновляется только вручную. Это фича, а не баг: гарантирует, что сырые изменения не просачиваются. Когда нужно обновить — явный `git pull`. |
| Дублирование `.venv`, `node_modules`, docker images между копиями | Приемлемая цена за изоляцию. Место на диске дешёвое, копии не связаны. |
| `remote` prod-копии указывает на локальный путь `file:///~/.../anything-to-anki` — если dev-папка переименована/удалена, prod-копия не сможет `git pull` | Документировать в `docs/running.md`. Если нужно — переставить remote на GitHub или другой путь одной командой. |
| Забыл, в какой копии запускаешь команду, редактируешь код в prod-копии | Бейдж в UI, плюс правило в `CLAUDE.md`. Физически ничего не мешает, но последствие минимально: нужно будет перенести правки в dev-копию через patch/stash. Данные prod не пострадают. |

## 14. Out of scope

Эти вещи **не** делаются в рамках этой задачи. У некоторых уже есть отдельные записи в `TASKS.md`.

- **Миграция `upgrade_schema` в Alembic** — отдельная задача. Эта функция остаётся как есть.
- **Фикс 117 pre-existing ruff errors** — отдельная задача. Эта работа не должна ни исправлять, ни ухудшать ruff-состояние (кроме файлов, которые трогаем напрямую).
- **Настройка удалённого remote (GitHub)** — prod-копия использует local file-based remote на dev-папку. Миграция на GitHub — отдельная задача, если захочется.
- **Автоматизация релиза в prod** — никаких скриптов «задеплоить». Обновление prod — ручная последовательность из трёх команд, и это сознательно.
- **Healthcheck / мониторинг prod-копии** — не добавляется.
- **Экспорт/импорт между dev и prod** (например, перенести hand-curated набор источников из prod в dev для отладки) — не делается. Если потребуется — копируется файл БД вручную, с полным пониманием последствий.
- **Обновление исторических спеков** в `docs/superpowers/specs/*` — они снапшот во времени, остаются как есть.
