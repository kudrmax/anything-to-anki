# AI-интеграция

AI используется для генерации значений слов, переводов, синонимов и примеров. Модель — Claude через `claude-agent-sdk`.

## Почему ai_proxy вынесен на хост (а не в Docker)

`claude-agent-sdk` авторизуется через системный CLI `claude`, а тот хранит токены в **macOS Keychain**. Keychain недоступен из Docker-контейнера, поэтому SDK просто не запустится внутри образа.

Решение — **отдельный процесс `ai_proxy.py` на хосте**, который оборачивает SDK в HTTP-API, а backend в контейнере ходит в него по `host.docker.internal:{8766|8767}`.

## Как всё связано

```
backend (в Docker)  ──HTTP──►  ai_proxy.py (на хосте)  ──SDK──►  claude CLI  ──►  Keychain
                              host.docker.internal:8766/8767
```

- **Dev**: ai_proxy на `:8766`, prod: `:8767` — два независимых процесса (в каждой рабочей копии свой `AI_PROXY_PORT` из `.env`), чтобы не мешали друг другу
- Запуск/остановка — автоматически через `make up` / `make down` (см. Makefile, `start_ai_proxy` / `stop_ai_proxy`)
- Логи — `make logs` (ai_proxy идёт одним потоком со всеми сервисами, префикс `ai_proxy`). Сам файл лога лежит в `.logs/ai_proxy.log` текущей рабочей копии

## Два адаптера в `infrastructure/adapters/`

- **`claude_ai_service.py`** — прямое использование `claude-agent-sdk`. Работает **только на хосте**, внутри `ai_proxy.py`. В контейнере не подключается.
- **`http_ai_service.py`** — HTTP-клиент к `ai_proxy`. Используется backend-контейнером. Именно этот адаптер регистрируется в `container.py` при обычном запуске.

Оба реализуют один и тот же порт `domain/ports/ai_service.py`, так что остальной код ничего не знает о различиях.

## Промпты

`config/prompts.yaml`. Все промпты в одном файле, загружаются через `PROMPTS_CONFIG_PATH` (монтируется в контейнер read-only). Менять промпты — только в `prompts.yaml`, никаких f-строк с промптами в коде.
