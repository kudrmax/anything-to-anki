# AI-интеграция

AI используется для генерации значений слов, переводов, синонимов и примеров. Модель — Claude через `claude-agent-sdk`.

## Почему ai_proxy — отдельный процесс

`claude-agent-sdk` авторизуется через системный CLI `claude`, а тот хранит токены в **macOS Keychain**. API-ключ не нужен, но SDK работает только там, где доступен залогиненный CLI.

Поэтому SDK изолирован в **отдельном процессе `ai_proxy.py`**, который оборачивает его в HTTP-API. Backend ходит в него по `AI_PROXY_URL` (`http://localhost:{8766|8767}`) и сам от `claude-agent-sdk` не зависит: пакет стоит в extras `[ai-proxy]` корневого `pyproject.toml`, а не в зависимостях backend.

Исторически разделение появилось, когда backend жил в Docker, откуда Keychain недоступен. Docker убран, граница осталась: backend знает только про HTTP-порт `AIService`.

## Как всё связано

```
backend (app, worker)  ──HTTP──►  ai_proxy.py  ──SDK──►  claude CLI  ──►  Keychain
                          localhost:8766/8767
```

- **Dev**: ai_proxy на `:8766`, prod: `:8767` — два независимых процесса (в каждой рабочей копии свой `AI_PROXY_PORT` из `.env`), чтобы не мешали друг другу
- Запуск/остановка — автоматически через `make up` / `make down` (см. Makefile, `start_ai_proxy` / `stop_ai_proxy`)
- Логи — `make logs` (ai_proxy идёт одним потоком со всеми сервисами, префикс `ai_proxy`). Сам файл лога лежит в `.logs/ai_proxy.log` текущей рабочей копии

## Адаптер в `infrastructure/adapters/`

**`http_ai_service.py`** — HTTP-клиент к `ai_proxy`, единственная реализация порта `domain/ports/ai_service.py`. Именно он регистрируется в `container.py`. Прямая работа с `claude-agent-sdk` живёт только в `ai_proxy.py`.

## Промпты

`config/prompts.yaml`. Все промпты в одном файле, путь по умолчанию можно переопределить через `PROMPTS_CONFIG_PATH`. Менять промпты — только в `prompts.yaml`, никаких f-строк с промптами в коде.
