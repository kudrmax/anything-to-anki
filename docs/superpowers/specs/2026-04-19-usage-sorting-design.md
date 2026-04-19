# Usage-группы как критерий сортировки target'ов — дизайн

## Проблема

Сортировка кандидатов учитывает частотность, фразовые глаголы, CEFR и количество вхождений, но не регистр/стиль слова. Слово `gonna` (informal) и `henceforth` (formal) с одинаковой частотностью показываются рядом, хотя для пользователя, изучающего разговорный английский, `gonna` полезнее.

Cambridge Dictionary содержит ~30K sense'ов с usage-метками (informal, formal, specialized и т.д.), которые уже парсятся в `CambridgeSense.usages`, но не используются.

## Решение

Добавить usage-группу как критерий сортировки кандидатов. Пользователь задаёт порядок групп в настройках (drag-and-drop), слова с более приоритетной группой показываются раньше. Фильтрация не меняется — только CEFR, как сейчас.

## Решения, принятые при брейншторме

| Вопрос | Решение | Альтернативы |
|---|---|---|
| Влияние на кандидатов | Только сортировка, без фильтрации | Фильтр + сортировка; числовые веса |
| Позиция в сортировке | После phrasal verbs, перед CEFR | После freq_band; после CEFR; после всех |
| Слова без usage-метки | Группа «Neutral», позиция задаётся пользователем | Фиксированный высокий приоритет; низкий приоритет; игнорировать |
| Хранение на кандидате | Распределение долей по группам (`dict[str, float]`) | Одна группа; множество без весов |
| Нет в Cambridge | `None` в БД, трактуется как neutral в коде | `{"neutral": 1.0}` в БД |
| Коннотация (disapproving/approving/humorous) | Отдельная группа | Объединить с Other |
| Мелкие метки (literary, trademark, child's word, figurative) | Группа Other | Отдельные группы |
| Отключение групп | Не реализуется (пока). Только порядок | Disabled-список |

## Usage-группы

8 групп. Raw-значения из Cambridge нормализуются при загрузке:

| Группа | Raw-значения из Cambridge |
|---|---|
| `neutral` | *(без метки — виртуальная группа)* |
| `informal` | informal, very informal, slang, infml |
| `formal` | formal, fml |
| `specialized` | specialized, specialist, specalized |
| `connotation` | disapproving, approving, humorous |
| `old-fashioned` | old-fashioned, old use, dated |
| `offensive` | offensive, very offensive, extremely offensive |
| `other` | literary, trademark, child's word, figurative, not standard |

Маппинг raw → группа — константа в infrastructure (Cambridge-адаптер).

## Хранение

### На кандидате

Новое поле `StoredCandidate.usage_distribution: dict[str, float] | None`.

Заполняется один раз при анализе текста — lookup в Cambridge по lemma + POS (аналогично Cambridge CEFR source — фильтрация entry по POS кандидата, fallback на все entry если POS не найден). Для каждого sense определяется группа, считается доля sense'ов в каждой группе:

```
"cool": 5 sense'ов → 3 neutral, 2 informal → {"neutral": 0.6, "informal": 0.4}
"gonna": 2 sense'а informal → {"informal": 1.0}
"procrastinate": 1 sense без метки → {"neutral": 1.0}
слово не найдено в Cambridge → None
```

**БД:** новая колонка `usage_distribution` (JSON text, nullable). Alembic-миграция. Backfill для существующих кандидатов — `NULL`.

### В настройках пользователя

Новый ключ в settings: `usage_group_order`. Значение — JSON-массив, определяющий порядок групп (индекс 0 = наивысший приоритет):

```json
["neutral", "informal", "formal", "specialized", "connotation", "old-fashioned", "offensive", "other"]
```

Это дефолтный порядок. Пользователь меняет через drag-and-drop в UI.

## Сортировка

### Порядок критериев

Было:
```
freq_band DESC → is_phrasal_verb DESC → cefr ASC → occurrences DESC
```

Стало:
```
freq_band DESC → is_phrasal_verb DESC → usage_rank ASC → cefr ASC → occurrences DESC
```

### Определение usage_rank

1. Берём `usage_distribution` кандидата
2. Если `None` — трактуем как neutral
3. Берём пользовательский `usage_group_order`
4. **Основная группа** = первая по пользовательскому порядку из тех, что присутствуют в distribution
5. `usage_rank` = индекс основной группы в порядке (0, 1, 2...)

### Изменение сигнатуры

`sort_by_relevance(candidates, usage_order)` — порядок групп передаётся параметром из use case, который читает настройки.

## Архитектура по слоям

### Domain

- **Value object** `UsageDistribution` — обёртка над `dict[str, float] | None`, метод `primary_group(order: list[str]) -> str` для определения основной группы
- **Поле** на `StoredCandidate`: `usage_distribution: UsageDistribution`
- **`candidate_sorting.py`**: новый параметр `usage_order: list[str]`, новый ключ сортировки `usage_rank`

### Application

- **`analyze_text.py`**: при создании кандидата — lookup usage из Cambridge, формирование distribution
- **`manage_settings.py`**: новый ключ `usage_group_order` с дефолтным значением
- **DTO**: `usage_distribution` в `StoredCandidateDTO`, `usage_group_order` в `SettingsDTO`
- **Use cases** с сортировкой: читают `usage_group_order` из settings, передают в `sort_by_relevance()`

### Infrastructure

- **Cambridge-адаптер**: константа `USAGE_GROUP_MAP: dict[str, str]` (raw → группа), функция/сервис для вычисления distribution по lemma
- **Alembic-миграция**: колонка `usage_distribution` (JSON text, nullable)
- **SQLAlchemy model**: маппинг JSON-колонки
- **API**: `usage_distribution` в response DTO, `usage_group_order` в settings endpoints

### Frontend

- **SettingsPage**: секция «Usage priority» — drag-and-drop список из 8 групп с пояснениями
- **PATCH `/api/settings`**: сохранение порядка групп

## UI настроек

Секция «Usage priority» в SettingsPage. Каждая группа — перетаскиваемый элемент:

```
↕ Neutral          — standard, unmarked words
↕ Informal         — slang, casual speech
↕ Formal           — formal register
↕ Specialized      — technical, domain-specific
↕ Connotation      — disapproving, approving, humorous
↕ Old-fashioned    — dated, archaic
↕ Offensive        — offensive language
↕ Other            — literary, trademark, etc.
```

Порядок сверху вниз = приоритет от высшего к низшему.

## Тестирование

Полное покрытие тестами — обязательное требование.

### Unit-тесты

- **`UsageDistribution` value object**: создание, `primary_group()` с разным порядком, `None` → neutral, пустой distribution, одна группа, несколько групп с разными долями
- **`USAGE_GROUP_MAP` нормализация**: все raw-значения маппятся в правильные группы, опечатки (infml, fml, specalized) нормализуются
- **Вычисление distribution из Cambridge sense'ов**: один sense, несколько sense'ов одной группы, несколько групп, sense'ы без usages → neutral, фильтрация по POS, fallback без POS
- **`candidate_sorting.sort_by_relevance()`**: usage_rank встаёт на правильную позицию между phrasal verbs и CEFR, разный пользовательский порядок меняет результат сортировки, кандидаты с `None` distribution трактуются как neutral
- **Settings**: дефолтный `usage_group_order`, сохранение и чтение кастомного порядка

### Integration-тесты

- **Полный pipeline**: текст → анализ → кандидаты в БД с usage_distribution → загрузка → сортировка с пользовательским порядком → проверка финального порядка
- **Миграция**: backfill существующих кандидатов → `NULL`, новые кандидаты получают distribution
- **API**: GET/PATCH settings с usage_group_order, response содержит usage_distribution на кандидатах
