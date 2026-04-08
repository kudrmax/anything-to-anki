# Spec 1 — Вынести промпты из БД в YAML-конфиг

**Дата:** 2026-04-08
**Статус:** утверждено

## Цель

Убрать из системы возможность редактирования промптов через БД/API/UI. Промпты становятся статичной конфигурацией в файле `config/prompts.yaml` в корне репозитория. Это позволяет видеть и править тексты промптов снаружи без изменения кода и без миграций БД, но исключает их редактирование пользователем через интерфейс.

## Мотивация

Сейчас промпты хранятся в таблице `prompt_templates`, сеедятся при старте из константы `_DEFAULT_SYSTEM_PROMPT` в `database.py`, редактируются через `SettingsPage` (API `GET /prompts`, `PUT /prompts/{function_key}`). Это избыточно: промпты — это внутренний артефакт качества продукта, а не пользовательская настройка. Хранение в БД порождает миграции при изменении текста, семантический drift между инсталляциями и бесполезную сложность (отдельная сущность, порт, репозиторий, use case, API, UI).

## Формат конфига

Файл: `config/prompts.yaml` в корне проекта.

Структура:

```yaml
ai:
  generate_meaning:
    user_template: 'Word: "{lemma}" ({pos})\nContext: "{context}"'
    system:
      intro: |
        <первый абзац текущего _DEFAULT_SYSTEM_PROMPT,
        без изменений>
      meaning: |
        <блок "For the 'meaning' field, provide: ..." целиком,
        LINE 1–4 остаются внутри (разделение на translation/synonyms —
        задача Spec 3)>
      ipa: |
        <блок "For the 'ipa' field, provide ..." без изменений>
```

**Правило переноса:** текст текущего промпта режется по секциям механически, без правок формулировок. Итоговая склейка `intro + "\n\n" + meaning + "\n\n" + ipa` должна давать строку, эквивалентную текущему `_DEFAULT_SYSTEM_PROMPT`.

## Архитектура

### Домен

Новый value object:

```
backend/domain/value_objects/prompts_config.py

@dataclass(frozen=True)
class PromptsConfig:
    generate_meaning_user_template: str
    generate_meaning_system: str  # уже склеенный из секций
```

Use cases принимают `PromptsConfig` через конструктор вместо `PromptRepository`. Инстанс — singleton, создаётся один раз при инициализации `Container`.

### Infrastructure

Новый модуль:

```
backend/infrastructure/config/prompts_loader.py

class PromptsLoader:
    def load(self, path: Path) -> PromptsConfig: ...
```

Реализация: читает YAML, извлекает `ai.generate_meaning.user_template` и секции `ai.generate_meaning.system.intro|meaning|ipa`, склеивает их через `"\n\n"` в правильном порядке, возвращает `PromptsConfig`. При отсутствии файла или обязательных ключей — бросает `ConfigError` (новое исключение в `domain/exceptions.py`).

Путь к конфигу — через env var `PROMPTS_CONFIG_PATH`. Дефолт в коде: относительный путь `config/prompts.yaml` относительно корня проекта. В Docker контейнере ожидается `/app/config/prompts.yaml`.

### Container

`backend/infrastructure/container.py`:
- Удалить фабрику `prompt_repository()` / `manage_prompts_use_case()`
- Добавить поле `_prompts_config: PromptsConfig`, инициализируемое в `__init__` через `PromptsLoader`
- `generate_meaning_use_case(session)` и `meaning_generation_use_case(session)` получают `_prompts_config` вместо `PromptRepository`

### Use cases

`backend/application/use_cases/generate_meaning.py`:
- Убрать поле `_prompt_repo`
- Добавить поле `_prompts_config: PromptsConfig`
- Вместо `self._prompt_repo.get_by_key(...)` → использовать `self._prompts_config.generate_meaning_user_template` и `...generate_meaning_system`
- Убрать ветку `if prompt is None: raise PromptNotFoundError` и импорт `PromptNotFoundError`

`backend/application/use_cases/run_generation_job.py` (`MeaningGenerationUseCase`):
- Аналогично: убрать `_prompt_repo`, добавить `_prompts_config`
- Убрать ветку `raise InvalidPromptError(...)` и связанный импорт
- `prompt.user_template.format(...)` → `self._prompts_config.generate_meaning_user_template.format(...)`
- `prompt.system_prompt` → `self._prompts_config.generate_meaning_system`

**Внимание:** `EnqueueMeaningGenerationUseCase` (`enqueue_meaning_generation.py`) **не использует** `PromptRepository` — менять его не нужно.

## Что удаляется

### Backend

- `backend/domain/entities/prompt_template.py`
- `backend/domain/ports/prompt_repository.py`
- `backend/domain/exceptions.py` → `PromptNotFoundError` (проверить грепом, что больше не используется)
- `backend/domain/exceptions.py` → `InvalidPromptError` (проверить грепом)
- `backend/application/use_cases/manage_prompts.py`
- `backend/application/dto/prompt_dtos.py`
- `backend/infrastructure/persistence/sqla_prompt_repository.py`
- `backend/infrastructure/api/routes/prompts.py` (роутер `/prompts`)
- Подключение роутера в `api/app.py`
- `backend/infrastructure/persistence/models.py` → `PromptTemplateModel`
- `backend/infrastructure/persistence/database.py` → константы `_DEFAULT_SYSTEM_PROMPT`, `_DEFAULT_USER_TEMPLATE` и их seed-логика
- `backend/infrastructure/container.py` → фабрика `prompt_repository()` и `manage_prompts_use_case()`

### Frontend

- `frontends/web/src/pages/SettingsPage.tsx` → секция редактирования промптов
- `frontends/web/src/api/client.ts` → методы `listPrompts`, `updatePrompt`
- `frontends/web/src/api/types.ts` → типы `PromptTemplate`, `UpdatePromptRequest`

### Тесты

- Удалить: тесты на `manage_prompts`, `sqla_prompt_repository`, `api/routes/prompts`

## Что добавляется

### Зависимости

- `PyYAML` в `backend/pyproject.toml`

### Новые файлы

- `config/prompts.yaml` в корне проекта
- `backend/src/backend/domain/value_objects/prompts_config.py`
- `backend/src/backend/infrastructure/config/prompts_loader.py`
- `backend/src/backend/infrastructure/config/__init__.py`
- Alembic-ревизия `0007_drop_prompt_templates.py` → `DROP TABLE prompt_templates`

### Тесты

- `tests/unit/infrastructure/test_prompts_loader.py`:
  - Парсит корректный YAML → возвращает `PromptsConfig` со склеенным system prompt
  - Отсутствующий файл → `ConfigError`
  - Отсутствующая секция → `ConfigError`
  - Порядок склейки: `intro + "\n\n" + meaning + "\n\n" + ipa`
- `tests/unit/application/test_generate_meaning.py` — обновить: использовать `PromptsConfig` вместо мока `PromptRepository`

## Docker

`docker-compose.yml`: монтировать `./config` в backend-контейнер read-only (`./config:/app/config:ro`). Env var `PROMPTS_CONFIG_PATH=/app/config/prompts.yaml` (или дефолт).

## Миграция существующих инсталляций

Alembic `0007_drop_prompt_templates.py` удаляет таблицу. Тексты промптов в существующих БД, если пользователь их редактировал, **теряются** — это намеренное поведение: промпт возвращается к единому каноническому виду из `config/prompts.yaml`.

## Критерии приёмки

- После запуска backend читает `config/prompts.yaml`, при отсутствии файла или ошибке парсинга падает со внятной ошибкой
- `GenerateMeaningUseCase` работает, используя промпт из конфига
- В БД нет таблицы `prompt_templates`
- В UI нет секции редактирования промптов
- API `/prompts` возвращает 404
- Все существующие тесты проходят; новые тесты на loader проходят
- `config/prompts.yaml` коммитится в репозиторий
- Текст итогового промпта (склейка секций) эквивалентен текущему `_DEFAULT_SYSTEM_PROMPT` (символ в символ, не считая `\n\n` между секциями)

## Порядок работ в плане

1. Добавить `PyYAML`, создать `PromptsConfig`, `PromptsLoader`, тесты loader
2. Создать `config/prompts.yaml` с переносом текущего текста
3. Обновить `Container`, `GenerateMeaningUseCase`, `EnqueueMeaningGenerationUseCase`
4. Обновить тесты use cases
5. Удалить backend-код: ports, entities, use cases, repositories, models, routes, seed-логику
6. Alembic-миграция drop table
7. Удалить frontend-код (SettingsPage секция, api client методы, types)
8. Обновить docker-compose
9. Финальный прогон всех тестов + `tsc -b`
