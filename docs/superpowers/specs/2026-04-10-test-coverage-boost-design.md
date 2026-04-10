# Test coverage boost — design

## Goal

Поднять покрытие тестами критичных модулей backend, сфокусировавшись на **реальной логике** (расчёты, ветвления, обработка ошибок), а не на маппинге DTO/route ↔ use case. Приоритет — то, что бьёт по продакшн-надёжности: AI-интеграция, очереди (arq), AnkiConnect.

## Baseline (worktree-test-coverage-boost @ start)

- **148 файлов, 4008 statements, 776 missing → 80.64%**
- **451 passed, 1 skipped, 9 xfailed, 1 xpassed** (clean baseline)

## Priority targets (по запросу пользователя)

| # | Модуль | Stmts | Cov | Why |
|---|---|---|---|---|
| P0 | `infrastructure/adapters/claude_ai_service.py` | 84 | **0%** | AI integration. Все error paths (auth, CLI not found, ProcessError) — реальная логика обработки исключений. |
| P0 | `application/use_cases/enqueue_meaning_generation.py` | 31 | **0%** | Очереди + сложная ветка CHRONOLOGICAL/RELEVANCE сортировки + батчинг по 15. |
| P0 | `application/use_cases/enqueue_media_generation.py` | 29 | **0%** | Очереди + та же ветвистость. |
| P0 | `infrastructure/adapters/http_ai_service.py` | 51 | **24%** | AI proxy client. ConnectError/HTTPStatusError/generic — error handling. |
| P1 | `infrastructure/adapters/anki_connect_connector.py` | 69 | **49%** | Anki integration. 5 публичных методов без тестов: `get_version`, `is_available`, `find_notes_by_target`, `add_notes`, `get_model_field_names`, `store_media_file`. Уже был баг с silently swallowed errors. |
| P1 | `application/use_cases/add_manual_candidate.py` | 46 | **22%** | Реальная логика: детект phrasal verb, fallback to surface_form analysis, occurrence counting. |
| P2 | `application/use_cases/run_generation_job.py` | 41 | **93%** | Закрыть missing paths: 54-57 (все candidates skipped) и 82 (cancel during processing). |
| P2 | `infrastructure/workers.py` | 57 | **95%** | Закрыть startup/shutdown lifecycle. |

**Что НЕ трогаем сейчас (mapping/routes):** `routes/generation.py`, `routes/media.py`, `routes/sources.py`, `routes/candidates.py` — это маппинг (request → use case → response). Лог ниже.

## Approach: TDD

Для каждого тест-кейса:

1. **Сформулировать**, что именно тест должен проверить (один наблюдаемый эффект).
2. **Написать тест**.
3. **Запустить** — он должен FAIL по правильной причине (либо потому, что код ещё не вызван, либо ошибка отличается от ожидаемой).
4. Если код уже существует и тест **сразу прошёл** — это допустимо для покрытия существующего поведения, но проверить, что тест действительно бьёт в нужный участок (через `pytest --cov` локально на этот файл).
5. Если тест **упал из-за бага** в проде — анализировать:
   - Маленький/очевидный → fix-коммит сразу + тест зелёный.
   - Крупный/архитектурный → `xfail` с комментарием `# xfail: bug — see tasks/<file>.md`, файл задачи в `tasks/`, продолжать.

## Bug handling policy (от пользователя)

- **Мелкие/очевидные баги** — чинить сразу отдельным fix-коммитом в worktree.
- **Крупные/архитектурные баги** — оставить `# TODO: ...` в коде, пометить тест `pytest.xfail`/`pytest.skip` со ссылкой, завести файл в `tasks/<topic>.md` с описанием.

## Mocking strategy

- **Domain ports** — мокаются через `unittest.mock.MagicMock`, как уже принято в проекте (см. `test_workers.py`).
- **`httpx.post`** — мокается через `unittest.mock.patch` с возвратом mock-response (`status_code`, `json()`, `raise_for_status()`).
- **`claude_agent_sdk.query`** — async generator, мокается через `patch` с `AsyncMock` или yield-функцией.
- **Никаких реальных сетевых вызовов** в unit-тестах. Никаких реальных Redis/AI/Anki.

## Coverage measurement

- Команда: `.venv/bin/python -m pytest --cov=backend/src/backend --cov-report=term --cov-report=json:coverage-final.json -q`
- Сравнение baseline → final по `percent_covered` и по приоритетным модулям.
- Никакой настройки `.coveragerc` или CI-gate в этой задаче — это отдельная инициатива.

## Out of scope (явно)

- Routes (`infrastructure/api/routes/*`) — маппинг, низкая ценность тестов.
- Container DI wiring (`infrastructure/container.py` 66%) — в основном construction, низкая логическая ценность.
- Alembic migration scripts (66-69%) — миграции тестируются вручную в dev/prod.
- Frontend.
- Реальные интеграционные тесты с Anki/AI proxy.
- Изменение архитектуры или рефакторинг продакшн-кода (только локальные fix-коммиты для маленьких багов).

## Expected outcome

- **Coverage:** 80.6% → ~87-90% (точная цифра зависит от количества missing lines, которые удастся закрыть).
- **Новые тесты:** ~50-60.
- **Файл итогового отчёта:** `docs/superpowers/specs/2026-04-10-test-coverage-boost-report.md` — quant + qual.
- **Все новые тесты** в существующих директориях `backend/tests/unit/{infrastructure,application}/`.
- **Все обнаруженные баги** задокументированы (либо как fix-коммиты, либо как файлы в `tasks/`).
