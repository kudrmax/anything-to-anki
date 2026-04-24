.PHONY: up down logs setup up-worktree down-worktree logs-worktree test coverage lint typecheck help migrate-paths _check_env _check_setup

# Читаем .env для Makefile-переменных (AI_PROXY_PORT, PORT, INSTANCE_ENV_NAME).
# -include не падает если файла нет; если .env создаётся правилом ниже,
# Make автоматически перечитывает Makefile с новыми переменными.
-include .env
export

# ── Константы ─────────────────────────────────────────────────────
AI_PID  := .pids/ai_proxy.pid
AI_LOG  := .logs/ai_proxy.log
APP_PID := .pids/app.pid
APP_LOG := .logs/app.log
WRK_PID := .pids/worker.pid
WRK_LOG := .logs/worker.log

# Цвет баннера: зелёный для prod, жёлтый для всего остального (dev и т.п.).
# Чисто визуальная разметка — совпадает с цветом бейджа в UI.
ifeq ($(INSTANCE_ENV_NAME),prod)
BANNER_COLOR := \033[1;32m
else
BANNER_COLOR := \033[1;33m
endif

# ── Вспомогательные макросы ────────────────────────────────────────
# Убить процесс по PID-файлу. $(1) — путь к PID-файлу, $(2) — название для лога.
define kill_by_pid
	@if [ -f $(1) ]; then \
	    pid=$$(cat $(1)); \
	    if kill -0 $$pid 2>/dev/null; then \
	        kill $$pid; \
	        echo "Stopped $(2) (PID $$pid)"; \
	    fi; \
	    rm -f $(1); \
	fi
endef

# Убить ai_proxy на порту $(1). Проверяем что это именно ai_proxy (grep по args),
# чтобы случайно не убить чужой процесс на том же порту.
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
	$(call kill_ai_proxy_on_port,$(AI_PROXY_PORT))
	@.venv/bin/python ai_proxy.py --port $(AI_PROXY_PORT) >> $(AI_LOG) 2>&1 & echo $$! > $(AI_PID); \
	    echo "ai_proxy started on port $(AI_PROXY_PORT) (PID $$(cat $(AI_PID)))"
endef

define start_app
	@mkdir -p .pids .logs
	@AI_PROXY_URL=http://localhost:$(AI_PROXY_PORT) \
	    .venv/bin/uvicorn backend.infrastructure.api.app:app \
	    --host 0.0.0.0 --port $(PORT) >> $(APP_LOG) 2>&1 & echo $$! > $(APP_PID); \
	    echo "app started on port $(PORT) (PID $$(cat $(APP_PID)))"
endef

define start_worker
	@mkdir -p .pids .logs
	@AI_PROXY_URL=http://localhost:$(AI_PROXY_PORT) \
	    .venv/bin/python -m backend.infrastructure.queue >> $(WRK_LOG) 2>&1 & echo $$! > $(WRK_PID); \
	    echo "worker started (PID $$(cat $(WRK_PID)))"
endef

define stop_ai_proxy
	$(call kill_ai_proxy_on_port,$(AI_PROXY_PORT))
	@rm -f $(AI_PID)
endef

# Автосоздание .env из .env.example.
# Make вызывает это правило когда -include .env не нашёл файл,
# после чего автоматически перечитывает Makefile — переменные подхватываются.
.env:
	@if [ -f .env.example ]; then \
	    cp .env.example .env; \
	    echo "Created .env from .env.example"; \
	else \
	    echo "ERROR: .env file missing and no .env.example found."; \
	    exit 1; \
	fi

_check_env:
	@if [ ! -f .env ]; then \
	    echo "ERROR: .env file missing. Copy .env.example to .env and fill in values."; \
	    exit 1; \
	fi

_check_setup:
	@if [ ! -d .venv ]; then \
	    echo "ERROR: .venv not found. Run 'make setup' first."; \
	    exit 1; \
	fi
	@if [ ! -d frontends/web/node_modules ]; then \
	    echo "ERROR: node_modules not found. Run 'make setup' first."; \
	    exit 1; \
	fi
	@command -v ffmpeg >/dev/null || (echo "ERROR: ffmpeg not installed. Run 'make setup' first." && exit 1)

##@ Установка
setup:  ## Одноразовая установка зависимостей (brew, Python, Node)
	@echo "=== Checking brew dependencies ==="
	@command -v brew >/dev/null || (echo "ERROR: Homebrew not installed. Install from https://brew.sh" && exit 1)
	@for pkg in python@3.12 node ffmpeg espeak; do \
	    if ! brew list $$pkg >/dev/null 2>&1; then \
	        echo "Installing $$pkg..."; \
	        HOMEBREW_BOTTLE_DOMAIN="" HOMEBREW_CORE_GIT_REMOTE="" HOMEBREW_BREW_GIT_REMOTE="" brew install $$pkg; \
	    else \
	        echo "$$pkg: already installed"; \
	    fi; \
	done
	@echo "\n=== Creating Python venv ==="
	@python3 -m venv .venv
	@.venv/bin/pip install -e "backend/[dev,tts]"
	@.venv/bin/pip install -e ".[ai-proxy]"
	@echo "\n=== Installing frontend dependencies ==="
	@cd frontends/web && npm install
	@echo "\n=== Setup complete. Run 'make up' to start. ==="

##@ Словари
_check_dictionaries_dir:
	@if [ -z "$${DICTIONARIES_DIR}" ]; then \
	    echo "ERROR: DICTIONARIES_DIR not set in .env. Set it to the path of your unified dictionaries folder."; \
	    exit 1; \
	fi

dict-rebuild: _check_setup _check_dictionaries_dir  ## Пересобрать словарный кэш с нуля
	@rm -f $${DICTIONARIES_DIR}/.cache/dict.db 2>/dev/null || true
	.venv/bin/python -m backend.cli.build_dict_cache $${DICTIONARIES_DIR}

dict-update: _check_setup _check_dictionaries_dir  ## Обновить словарный кэш если JSON изменились
	@.venv/bin/python -m backend.cli.build_dict_cache $${DICTIONARIES_DIR} --if-changed

##@ Запуск (читает .env)
up: _check_env _check_setup dict-update  ## Запустить (ai_proxy + app + worker)
	@echo "Building frontend..."
	@cd frontends/web && npm run build
	$(call start_ai_proxy)
	$(call start_app)
	$(call start_worker)
	@printf "\n$(BANNER_COLOR)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "  AnythingToAnki  [instance: %s]\n" "$(INSTANCE_ENV_NAME)"
	@printf "  → http://localhost:%s\n" "$(PORT)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "\033[0m\n"

up-worktree: _check_env _check_setup dict-update  ## Запустить worktree (WORKTREE_PORT, сносит предыдущий)
	@echo "Building frontend..."
	@cd frontends/web && npm run build
	$(call kill_ai_proxy_on_port,$(WORKTREE_AI_PROXY_PORT))
	@mkdir -p .pids .logs
	@.venv/bin/python ai_proxy.py --port $(WORKTREE_AI_PROXY_PORT) >> $(AI_LOG) 2>&1 & echo $$! > .pids/ai_proxy_wt.pid; \
	    echo "ai_proxy started on port $(WORKTREE_AI_PROXY_PORT)"
	@AI_PROXY_URL=http://localhost:$(WORKTREE_AI_PROXY_PORT) \
	    INSTANCE_ENV_NAME=worktree \
	    .venv/bin/uvicorn backend.infrastructure.api.app:app \
	    --host 0.0.0.0 --port $(WORKTREE_PORT) >> .logs/app_wt.log 2>&1 & echo $$! > .pids/app_wt.pid; \
	    echo "app started on port $(WORKTREE_PORT)"
	@AI_PROXY_URL=http://localhost:$(WORKTREE_AI_PROXY_PORT) \
	    .venv/bin/python -m backend.infrastructure.queue >> .logs/worker_wt.log 2>&1 & echo $$! > .pids/worker_wt.pid; \
	    echo "worker started"
	@printf "\n\033[1;33m"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "  AnythingToAnki  [worktree]\n"
	@printf "  → http://localhost:%s\n" "$(WORKTREE_PORT)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "\033[0m\n"

down:  ## Остановить
	$(call kill_by_pid,$(APP_PID),app)
	$(call kill_by_pid,$(WRK_PID),worker)
	$(call stop_ai_proxy)

down-worktree:  ## Остановить worktree
	$(call kill_by_pid,.pids/app_wt.pid,worktree app)
	$(call kill_by_pid,.pids/worker_wt.pid,worktree worker)
	$(call kill_by_pid,.pids/ai_proxy_wt.pid,worktree ai_proxy)

logs:  ## Логи app + worker + ai_proxy одним потоком
	@trap 'kill 0' INT TERM; \
	tail -F $(APP_LOG) 2>/dev/null | sed -l 's/^/app             | /' & \
	tail -F $(WRK_LOG) 2>/dev/null | sed -l 's/^/worker          | /' & \
	tail -F $(AI_LOG) 2>/dev/null | sed -l 's/^/ai_proxy        | /' & \
	wait

logs-worktree:  ## Логи worktree (app + worker + ai_proxy)
	@trap 'kill 0' INT TERM; \
	tail -F .logs/app_wt.log 2>/dev/null | sed -l 's/^/app             | /' & \
	tail -F .logs/worker_wt.log 2>/dev/null | sed -l 's/^/worker          | /' & \
	tail -F $(AI_LOG) 2>/dev/null | sed -l 's/^/ai_proxy        | /' & \
	wait

##@ Разработка
test: _check_setup  ## Запустить тесты
	.venv/bin/python -m pytest

coverage: _check_setup  ## Тесты с отчётом покрытия
	.venv/bin/python -m pytest --cov --cov-report=term

test-ai: _check_setup  ## Интеграционные тесты AI (реальный ai_proxy + Claude API)
	.venv/bin/python -m pytest -m ai_integration -v

lint: _check_setup  ## Линтинг (ruff)
	.venv/bin/ruff check .

typecheck: _check_setup  ## Проверка типов (mypy)
	.venv/bin/mypy backend/src

##@ Миграция
migrate-paths: _check_setup  ## Мигрировать Docker-пути в БД (dry-run, APPLY=1 для применения)
	.venv/bin/python scripts/migrate_docker_paths.py $(if $(APPLY),--apply)

##@ Прочее
help:  ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	  /^[a-zA-Z_-]+:.*##/ { printf "  %-14s %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
	@echo ""
