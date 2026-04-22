.PHONY: up up-worktree down down-worktree logs logs-worktree test coverage lint typecheck help _python_dev _check_env

# Читаем .env для Makefile-переменных (AI_PROXY_PORT, PORT, INSTANCE_ENV_NAME).
# docker compose читает .env сам — это только для ai_proxy и echo.
# -include не падает если файла нет; если .env создаётся правилом ниже,
# Make автоматически перечитывает Makefile с новыми переменными.
-include .env
export

# ── Константы ─────────────────────────────────────────────────────
AI_VENV := .venv-ai-proxy
AI_PID  := .pids/ai_proxy.pid
AI_LOG  := .logs/ai_proxy.log

# Цвет баннера: зелёный для prod, жёлтый для всего остального (dev и т.п.).
# Чисто визуальная разметка — совпадает с цветом бейджа в UI.
ifeq ($(INSTANCE_ENV_NAME),prod)
BANNER_COLOR := \033[1;32m
else
BANNER_COLOR := \033[1;33m
endif

# ── Вспомогательные макросы ────────────────────────────────────────
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

# Всегда перезапускает ai_proxy: убивает старый процесс и стартует новый.
# Использует AI_PROXY_PORT из .env.
define start_ai_proxy
	@mkdir -p .pids .logs
	@[ -d $(AI_VENV) ] || (echo "Creating AI proxy venv..." && \
	    python3 -m venv $(AI_VENV))
	@$(AI_VENV)/bin/pip install -e ".[ai-proxy]"
	$(call kill_ai_proxy_on_port,$(AI_PROXY_PORT))
	@$(AI_VENV)/bin/python ai_proxy.py --port $(AI_PROXY_PORT) >> $(AI_LOG) 2>&1 & echo $$! > $(AI_PID); \
	    echo "AI proxy started on port $(AI_PROXY_PORT) (PID $$(cat $(AI_PID)))"
endef

# Проверить что все контейнеры живы после docker compose up.
# $(1) — префикс env-переменных для docker compose (пустой для основного инстанса).
define check_services
	@sleep 2; \
	failed=$$($(1) docker compose ps --status exited --status restarting --format '{{.Service}}' 2>/dev/null); \
	if [ -n "$$failed" ]; then \
	    printf "\n\033[1;31m✗ Сервисы не запустились: %s\033[0m\n" "$$failed"; \
	    printf "  Логи: make logs\n\n"; \
	    $(1) docker compose logs --tail 30 $$failed; \
	    exit 1; \
	fi
endef

# Остановить ai_proxy.
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

# Проверить что .env существует.
_check_env:
	@if [ ! -f .env ]; then \
	    echo "ERROR: .env file missing. Copy .env.example to .env and fill in values."; \
	    exit 1; \
	fi

##@ Запуск (читает .env)
up: _check_env  ## Запустить (ai_proxy + docker compose)
	$(call start_ai_proxy)
	docker compose up -d --build
	$(call check_services,)
	@printf "\n$(BANNER_COLOR)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "  AnythingToAnki  [instance: %s]\n" "$(INSTANCE_ENV_NAME)"
	@printf "  → http://localhost:%s\n" "$(PORT)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "\033[0m\n"

up-worktree: _check_env  ## Запустить worktree (WORKTREE_PORT, сносит предыдущий worktree)
	@# Симлинк dictionaries на main worktree (submodule там уже инициализирован).
	@# В worktree git создаёт пустую директорию dictionaries/ (submodule placeholder),
	@# поэтому проверяем наличие реальных файлов, а не просто -e.
	@main=$$(git worktree list --porcelain | head -1 | awk '{print $$2}'); \
	if [ "$$main" != "$$(pwd)" ]; then \
	    if [ ! -f "$$main/dictionaries/cefr/efllex.tsv" ]; then \
	        echo "ERROR: dictionaries submodule not initialized in main worktree."; \
	        echo "Run:  cd $$main && git submodule update --init dictionaries"; \
	        exit 1; \
	    fi; \
	    if [ -d dictionaries ] && [ ! -L dictionaries ] && [ -z "$$(ls -A dictionaries 2>/dev/null)" ]; then \
	        rmdir dictionaries; \
	    fi; \
	    if [ ! -e dictionaries ]; then \
	        ln -s "$$main/dictionaries" dictionaries; \
	        echo "Symlinked dictionaries → main worktree"; \
	    fi; \
	fi
	@# Остановить предыдущий worktree на этих портах (если есть)
	@containers=$$(docker ps --format '{{.ID}} {{.Ports}}' | grep '$(WORKTREE_PORT)->' | awk '{print $$1}'); \
	if [ -n "$$containers" ]; then \
	    echo "Stopping previous worktree on port $(WORKTREE_PORT)..."; \
	    echo "$$containers" | xargs docker stop; \
	fi
	$(call kill_ai_proxy_on_port,$(WORKTREE_AI_PROXY_PORT))
	@mkdir -p .pids .logs
	@[ -d $(AI_VENV) ] || (echo "Creating AI proxy venv..." && \
	    python3 -m venv $(AI_VENV))
	@$(AI_VENV)/bin/pip install -e ".[ai-proxy]"
	@$(AI_VENV)/bin/python ai_proxy.py --port $(WORKTREE_AI_PROXY_PORT) >> $(AI_LOG) 2>&1 & echo $$! > $(AI_PID); \
	    echo "AI proxy started on port $(WORKTREE_AI_PROXY_PORT) (PID $$(cat $(AI_PID)))"
	PORT=$(WORKTREE_PORT) AI_PROXY_PORT=$(WORKTREE_AI_PROXY_PORT) \
	    COMPOSE_PROJECT_NAME=anything-anki-worktree \
	    INSTANCE_ENV_NAME=worktree \
	    docker compose up -d --build
	$(call check_services,PORT=$(WORKTREE_PORT) AI_PROXY_PORT=$(WORKTREE_AI_PROXY_PORT) COMPOSE_PROJECT_NAME=anything-anki-worktree)
	@printf "\n$(BANNER_COLOR)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "  AnythingToAnki  [worktree]\n"
	@printf "  → http://localhost:%s\n" "$(WORKTREE_PORT)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "\033[0m\n"

down:  ## Остановить
	docker compose down
	$(call stop_ai_proxy)

down-worktree:  ## Остановить worktree-контейнеры
	docker compose -p anything-anki-worktree down
	$(call stop_ai_proxy)

logs:  ## Логи app + worker + redis + ai_proxy одним потоком
	@trap 'kill 0' INT TERM; \
	docker compose logs -f & \
	tail -F $(AI_LOG) 2>/dev/null | sed -l 's/^/ai_proxy        | /' & \
	wait

logs-worktree:  ## Логи worktree (app + worker + redis + ai_proxy)
	@trap 'kill 0' INT TERM; \
	docker compose -p anything-anki-worktree logs -f & \
	tail -F $(AI_LOG) 2>/dev/null | sed -l 's/^/ai_proxy        | /' & \
	wait

##@ Разработка
_python_dev:
	@[ -d .venv ] || python3 -m venv .venv
	@.venv/bin/pip install -e "backend/[dev]"

test: _python_dev  ## Запустить тесты
	.venv/bin/python -m pytest

coverage: _python_dev  ## Тесты с отчётом покрытия
	.venv/bin/python -m pytest --cov --cov-report=term

test-ai: _python_dev  ## Интеграционные тесты AI (реальный ai_proxy + Claude API)
	.venv/bin/python -m pytest -m ai_integration -v

lint: _python_dev  ## Линтинг (ruff)
	.venv/bin/ruff check .

typecheck: _python_dev  ## Проверка типов (mypy)
	.venv/bin/mypy backend/src

backfill-breakdowns:  ## Заполнить cefr_breakdowns для старых кандидатов (DRY_RUN=1 для пробного запуска)
	docker compose exec app python /app/scripts/backfill_cefr_breakdowns.py $(if $(DRY_RUN),--dry-run)

##@ Прочее
help:  ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	  /^[a-zA-Z_-]+:.*##/ { printf "  %-14s %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
	@echo ""
