.PHONY: dev-up dev-down dev-logs dev-logs-ai \
        prod-up prod-down prod-logs prod-logs-ai \
        test lint typecheck help _python_dev

# ── Константы ─────────────────────────────────────────────────────
DEV_PROJECT  := anything-anki-dev
PROD_PROJECT := anything-anki-prod
DEV_PORT     := 17832
PROD_PORT    := 17833
DEV_AI_PORT  := 8766
PROD_AI_PORT := 8767
DEV_AI_PID   := .pids/ai_proxy_dev.pid
PROD_AI_PID  := .pids/ai_proxy_prod.pid
DEV_AI_LOG   := .logs/ai_proxy_dev.log
PROD_AI_LOG  := .logs/ai_proxy_prod.log
AI_VENV      := .venv-ai-proxy

# ── Вспомогательные макросы ────────────────────────────────────────
# Убить ai_proxy на порту $(1).
# Ищем процесс по порту (lsof), затем проверяем что это именно ai_proxy (grep по args),
# чтобы случайно не убить чужой процесс на том же порту.
define kill_ai_proxy_on_port
	@pid=$$(lsof -ti :$(1) 2>/dev/null); \
	if [ -n "$$pid" ] && ps -p $$pid -o args= 2>/dev/null | grep -q ai_proxy; then \
	    kill $$pid 2>/dev/null || true; \
	    echo "Killed ai_proxy on port $(1) (PID $$pid)"; \
	    sleep 0.5; \
	fi
endef

# Всегда перезапускает ai_proxy: убивает старый процесс (если есть) и стартует новый.
# Аргументы: $(1) PID-файл, $(2) лог-файл, $(3) порт.
# Использует отдельный лёгкий venv (AI_VENV) — создаётся автоматически при первом запуске.
define start_ai_proxy
	@mkdir -p .pids .logs
	@[ -d $(AI_VENV) ] || (echo "Creating AI proxy venv..." && \
	    python3 -m venv $(AI_VENV) && \
	    $(AI_VENV)/bin/pip install -e ".[ai-proxy]")
	$(call kill_ai_proxy_on_port,$(3))
	@$(AI_VENV)/bin/python ai_proxy.py --port $(3) >> $(2) 2>&1 & echo $$! > $(1); \
	    echo "AI proxy started on port $(3) (PID $$(cat $(1)))"
endef

# Остановить ai_proxy: убить процесс на порту $(2), удалить PID-файл $(1).
define stop_ai_proxy
	$(call kill_ai_proxy_on_port,$(2))
	@rm -f $(1)
endef

##@ Dev (localhost:17832, dev БД, ai_proxy :8766)
dev-up:  ## Запустить в фоне
	@echo "→ http://localhost:$(DEV_PORT)"
	$(call start_ai_proxy,$(DEV_AI_PID),$(DEV_AI_LOG),$(DEV_AI_PORT))
	AI_PROXY_URL=http://host.docker.internal:$(DEV_AI_PORT) \
	    docker compose -p $(DEV_PROJECT) up -d --build

dev-down:  ## Остановить
	docker compose -p $(DEV_PROJECT) down
	$(call stop_ai_proxy,$(DEV_AI_PID),$(DEV_AI_PORT))

dev-logs:  ## Логи контейнера
	docker compose -p $(DEV_PROJECT) logs -f

dev-logs-ai:  ## Логи ai_proxy
	tail -f $(DEV_AI_LOG)

##@ Prod (localhost:17833, prod БД, ai_proxy :8767)
prod-up:  ## Запустить в фоне
	@echo "→ http://localhost:$(PROD_PORT)"
	$(call start_ai_proxy,$(PROD_AI_PID),$(PROD_AI_LOG),$(PROD_AI_PORT))
	PORT=$(PROD_PORT) APP_ENV=production \
	AI_PROXY_URL=http://host.docker.internal:$(PROD_AI_PORT) \
	    docker compose -p $(PROD_PROJECT) up -d --build

prod-down:  ## Остановить
	docker compose -p $(PROD_PROJECT) down
	$(call stop_ai_proxy,$(PROD_AI_PID),$(PROD_AI_PORT))

prod-logs:  ## Логи контейнера
	docker compose -p $(PROD_PROJECT) logs -f

prod-logs-ai:  ## Логи ai_proxy
	tail -f $(PROD_AI_LOG)

##@ Разработка
_python_dev:
	@[ -d .venv ] || python3 -m venv .venv
	@.venv/bin/pip install -e "backend/[dev]"

test: _python_dev  ## Запустить тесты
	.venv/bin/python -m pytest

lint: _python_dev  ## Линтинг (ruff)
	.venv/bin/ruff check .

typecheck: _python_dev  ## Проверка типов (mypy)
	.venv/bin/mypy backend/src

##@ Прочее
help:  ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	  /^[a-zA-Z_-]+:.*##/ { printf "  %-14s %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
	@echo ""
