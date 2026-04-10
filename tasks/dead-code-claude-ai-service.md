# Dead code: ClaudeAIService

**Found during:** test coverage boost session, 2026-04-10.

**Status:** Not blocking. Recommend deletion or honest documentation.

## Что не так

`backend/src/backend/infrastructure/adapters/claude_ai_service.py` — реализация порта `AIService` через прямой вызов `claude_agent_sdk` (84 statements). При этом:

1. Модуль **нигде не импортируется** в backend (`grep -rn "ClaudeAIService" backend/src/` → только определение).
2. `Container` создаёт исключительно `HttpAIService` (см. `container.py:30, 243, 257`), потому что backend живёт в Docker, где `claude` CLI / Keychain auth недоступен.
3. `claude-agent-sdk` даже **не входит в backend dependencies** (`backend/pyproject.toml` его не содержит). Он — `optional-dep` корневого `pyproject.toml` под extras `[ai-proxy]` и ставится только в `.venv-ai-proxy/` для запуска `ai_proxy.py` на хосте.

То есть `ClaudeAIService` — это код, который физически не может быть инстанцирован в продакшн-окружении (ImportError на `from claude_agent_sdk import ...`).

## Почему это важно

- 84 строки нерабочего кода, которые мутят carrier coverage статистику.
- Создаёт ложную иллюзию, что у `AIService` есть две реализации; на деле есть одна — `HttpAIService` через ai_proxy.
- При попытке покрыть тестами — приходится в test venv ставить `claude-agent-sdk` ради кода, который никогда не будет вызван в проде.

## Варианты решения

1. **Удалить** `claude_ai_service.py` целиком. Самый честный путь: отражает реальную архитектуру.
2. **Перенести в `ai_proxy.py`**: вся логика в `_async_generate` / `_async_generate_batch` (system prompt, batch schema, error mapping) дублирует то, что уже есть в `ai_proxy.py`. Можно унифицировать, оставив одну точку правды.
3. **Оставить как есть**, но добавить module-level комментарий-warning «не используется, оставлено как референс».

Рекомендуемый — #1 (удалить). Если когда-нибудь понадобится in-process Claude (например, если backend выйдет из Docker) — восстановить из git.

## Дополнительная находка: degraded error handling

При написании тестов выяснилось, что **внешние `except` блоки в `generate_meaning` и `generate_meanings_batch` — недостижимы**:

```python
def generate_meaning(self, system_prompt, user_prompt):
    try:
        return asyncio.run(self._async_generate(...))
    except AIServiceError:
        raise
    except CLINotFoundError as e:                        # ← unreachable
        raise AIServiceError("Claude Code CLI not found...") from e
    except CLIConnectionError as e:                       # ← unreachable
        ...
    except ProcessError as e:                             # ← unreachable
        ...
    except Exception as e:                                # ← unreachable
        ...
```

Причина: внутри `_async_generate` стоит общий `try/except Exception`, который ловит ВСЁ (включая `CLINotFoundError`, `CLIConnectionError`, `ProcessError`) и оборачивает в `AIServiceError(detail)`. Внешний `try` ловит этот `AIServiceError` и просто пробрасывает (`except AIServiceError: raise`). Специализированные ветки ниже физически недостижимы.

**Эффект:** вместо понятного сообщения «Claude Code CLI not found. Install it at https://claude.ai/download» пользователь получает что-то вроде «AI service error: <raw exception text>». Установочный хинт, hint про логин и хинт про exit code не всплывают никогда.

Это видно в покрытии: после написания 17 тестов файл достиг 81% — оставшиеся 16 непокрытых строк — это ровно строки 84–95 и 153–164, то есть всё четыре `except` в обёртках обоих методов.

## В рамках текущей сессии

- Тесты написаны (`backend/tests/unit/infrastructure/test_claude_ai_service.py`, 17 штук) и закреплены за **текущим** поведением (CLI* errors → AIServiceError с raw сообщением, без хинтов). Это regression guard.
- Сам прод-код **не правил** — модуль dead, исправление error mapping здесь смысла не имеет; правильное действие — удалить файл.

## Действие, которое я предлагаю принять решение по нему вне сессии

Удалить файл `claude_ai_service.py` и тесты `test_claude_ai_service.py`. Если в будущем понадобится — взять из git history. Текущая прод-архитектура — `HttpAIService` → `ai_proxy.py` (на хосте, с `claude-agent-sdk`) — не зависит от этого файла никак.
