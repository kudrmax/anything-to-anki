# План рефакторинга pipeline выбора границ фрагмента

Контекст: после Wave 1 + Wave 2 (см. `fragment-boundaries.md`) код работает (20/22 размеченных кейсов), но архитектурно неудобен. Нужен рефакторинг ради «понятных шагов с понятными именами», конфига вместо констант в коде, и возможности включать/выключать правила и источники кандидатов одной строкой.

Этот документ — план **рефакторинга, не нового функционала**. Поведение должно остаться идентичным, защищённое регрессионным тестом `test_full_pipeline_marked_fragments.py`.

---

## Часть 1. Что плохо в текущем коде (review)

Все пути относительно `backend/src/backend/`.

1. **`_select_best_fragment` — god-method** в use case (`application/use_cases/analyze_text.py:183-279`). ~90 строк, 4 источника кандидатов, фильтрация, скоринг и fallback — всё в одной функции. Это бизнес-логика выбора фрагмента, она должна жить в domain.

2. **Генерация кандидатов захардкожена inline** (`analyze_text.py:210-243`). Каждый источник — собственный `for`-цикл. Чтобы выключить источник — комментировать блок. Чтобы добавить новый — править метод. Нет общего интерфейса.

3. **Скоринг — анонимная функция** (`analyze_text.py:269-277`). Tuple `(unknown, length_penalty, content_count)` вшит. Веса не конфигурируются.

4. **Константа `LENGTH_HARD_CAP_CONTENT_WORDS`** живёт в use case (`analyze_text.py:34`), `MIN_FRAGMENT_CONTENT_WORDS` — в `boundary_cleaner.py:9`. Настройки одной фичи разбросаны.

5. **`_count_unknowns_in_fragment`** — доменная логика в use case (`analyze_text.py:166-181`). Препятствует выносу скоринга в domain без callback/порта.

6. **`BoundaryCleaner._should_strip_*` — длинные if-лестницы** (`boundary_cleaner.py:73-168`). Каждое strip-правило (CCONJ, relativizer, ADP-без-объекта, PRON-subject, PRP$, AUX/PART) — жёстко в коде. Добавление/выключение — правка кода.

7. **Модульные константы boundary cleaner** (`boundary_cleaner.py:12-36`) — `_LEFT_STRIP_POS`, `_RIGHT_STRIP_POS` и т.д. — private с подчёркиванием, не настраиваются. Они хотят быть конфигом.

8. **`ClauseFinder`** заточен только на verb subtrees. Нет общего интерфейса «источник кандидатов».

9. **`FragmentExtractor`** — три обязанности в одном классе: legacy-лестница, render-хелпер, extract_indices. `render` — чистая функция, не нуждается в инстансе.

10. **Дублирование `count_content_words`** — три копии (`fragment_extractor.py:127`, `boundary_cleaner.py:172`, inline в `analyze_text.py:254-258, 271-275`).

11. **Дублирование `collect_subtree_in_sentence`** — три копии (`fragment_extractor.py:96`, `clause_finder.py:43`, `analyze_text.py:282`).

12. **Fallback неявен** (`analyze_text.py:263-267`). «Если все кандидаты отпали — cleaned legacy». Должно быть явным шагом pipeline.

13. **Тест-дисциплина:** unit-тесты `test_boundary_cleaner.py` тестируют поведение через публичный API, что хорошо. Но чтобы выключить правило в тесте — только monkeypatch private константы. Плохо.

14. **Нет единого места, где видно «что делает pipeline».** Чтобы понять алгоритм — открыть 4 файла и сопоставить.

15. **`render` используется только для финального текста** (`analyze_text.py:96, 150`). Не должен жить как метод класса `FragmentExtractor`.

---

## Часть 2. Целевая архитектура

### Pipeline с именованными шагами

Новый доменный сервис **`FragmentSelector`** в `domain/services/fragment_selection/selector.py`. Use case вызывает только `selector.select(...)`.

```
Шаг 1. GenerateCandidates  — список CandidateSource → list[Candidate]
Шаг 2. CleanBoundaries     — BoundaryCleaner на каждый кандидат
Шаг 3. FilterCandidates    — отсев потерявших target / ниже min content / дубли
Шаг 4. ScoreCandidates     — Scorer (настраиваемая функция)
Шаг 5. SelectBest          — argmin по score
Шаг 6. FallbackIfEmpty     — cleaned legacy если все отвалились
```

Каждый шаг — отдельный метод `_step_N_name` (5-15 строк). Читается сверху вниз за 10 секунд.

### Ключевые абстракции

Все в `domain/services/fragment_selection/`:

- **`CandidateSource` (Protocol).** `generate(tokens, target_index) -> Iterable[list[int]]`. Реализации:
  - `VerbSubtreeSource` — текущий `ClauseFinder.find_pieces`
  - `AncestorChainSource` — текущий цикл «target → head → head.head → ROOT»
  - `SentenceSource` — вся sentence
  - `LegacyExtractorSource` — обёртка над `FragmentExtractor.extract_indices`

- **`StripRule` (Protocol).** `applies(tokens, indices, edge: Edge) -> bool` где `Edge ∈ {LEFT, RIGHT}`. Каждое текущее strip-правило — отдельный мини-класс 10-20 строк.

- **`Scorer` (Protocol).** `score(candidate, tokens, context) -> tuple[...]`. По умолчанию `DefaultScorer` реализует текущее `(unknown_count, length_penalty, content_count)` с весами и `length_hard_cap` из конфига. Принимает `UnknownCounter` через конструктор.

- **`UnknownCounter` (callable).** `Callable[[list[int], list[TokenData]], int]`. Use case строит замыкание, передаёт в `selector.select(...)`. Так `_count_unknowns_in_fragment` остаётся в use case (зависит от CEFR), `FragmentSelector` остаётся в domain.

- **`render(tokens, indices) -> str`** — чистая функция модуля в `rendering.py`.

- **`count_content_words` / `collect_subtree_in_sentence`** — общие функции в `utils.py`. Дубликаты удаляются.

### Конфиг

Файл: **`domain/value_objects/fragment_selection_config.py`** (frozen dataclass, чистый domain, без зависимостей).

```python
@dataclass(frozen=True)
class ScoringConfig:
    length_hard_cap_content_words: int = 25
    weight_unknown: int = 1          # 0 = выключить фактор
    weight_length_penalty: int = 1
    weight_content_count: int = 1
    prefer_shorter_on_tie: bool = True

@dataclass(frozen=True)
class CleanupConfig:
    min_fragment_content_words: int = 5
    keep_right_punct: frozenset[str] = frozenset({".", "!", "?"})
    enabled_rules: tuple[str, ...] = (
        "punctuation",
        "left_cconj_sconj",
        "left_relativizer",
        "right_cconj_sconj_det",
        "right_trailing_intj",
        "right_dangling_adp",
        "right_dangling_subject_pronoun",
        "right_possessive_pronoun",
        "right_relative_pronoun",
        "right_dangling_aux_part",
    )
    right_strip_pron_lemmas: frozenset[str] = frozenset({"i","you","he","she","it","we","they"})
    left_strip_relativizers: frozenset[str] = frozenset({"that","which","who","whom","whose"})
    subject_deps: frozenset[str] = frozenset({"nsubj","nsubjpass"})
    aux_deps: frozenset[str] = frozenset({"aux","auxpass"})

@dataclass(frozen=True)
class CandidateSourcesConfig:
    enabled_sources: tuple[str, ...] = (
        "verb_subtree",
        "ancestor_chain",
        "sentence",
        "legacy_extractor",
    )

@dataclass(frozen=True)
class FragmentSelectionConfig:
    sources: CandidateSourcesConfig = CandidateSourcesConfig()
    cleanup: CleanupConfig = CleanupConfig()
    scoring: ScoringConfig = ScoringConfig()
    fallback_to_cleaned_legacy: bool = True
```

**Принципы:**
- Frozen dataclass — pure domain, zero-dep. Pydantic не нужен.
- Строковые имена правил/источников в `enabled_*` — выключить правило = одна строка `dataclasses.replace`.
- **Реестр** (`STRIP_RULES: dict[str, StripRule]`, `CANDIDATE_SOURCES: dict[str, type[CandidateSource]]`) в `registry.py`. Просто dict, не плагин-механизм.
- Use case получает `FragmentSelectionConfig` через конструктор из `container.py`. По умолчанию `FragmentSelectionConfig()`.

**Добавить кастомный источник** = создать класс в `sources/`, зарегистрировать в `registry.py`, добавить имя в `enabled_sources`. Три изменения, никакого перетряхивания use case.

### Файловая структура

```
backend/src/backend/domain/services/fragment_selection/
    __init__.py                  # re-export FragmentSelector и FragmentSelectionConfig
    selector.py                  # class FragmentSelector (pipeline-оркестратор)
    candidate.py                 # @dataclass(frozen=True) Candidate(indices, source_name)
    sources/
        __init__.py
        base.py                  # Protocol CandidateSource
        verb_subtree.py          # VerbSubtreeSource (ex-ClauseFinder)
        ancestor_chain.py        # AncestorChainSource
        sentence.py              # SentenceSource
        legacy_extractor.py      # LegacyExtractorSource (обёртка)
    cleanup/
        __init__.py
        cleaner.py               # class BoundaryCleaner (тонкий: цикл + применение)
        rules.py                 # Protocol StripRule + конкретные правила
    scoring/
        __init__.py
        scorer.py                # Protocol Scorer + DefaultScorer
    rendering.py                 # render(tokens, indices) -> str
    utils.py                     # count_content_words, collect_subtree_in_sentence
    registry.py                  # STRIP_RULES, CANDIDATE_SOURCES

backend/src/backend/domain/value_objects/
    fragment_selection_config.py  # FragmentSelectionConfig (+ подконфиги)
```

**Удалить:**
- `domain/services/clause_finder.py` → уезжает в `sources/verb_subtree.py`
- `domain/services/boundary_cleaner.py` → уезжает в `cleanup/`
- `domain/services/fragment_extractor.py` → `render` в `rendering.py`, `extract_indices` в `sources/legacy_extractor.py`, остальное удаляется

**В `analyze_text.py`:**
- Убрать `LENGTH_HARD_CAP_CONTENT_WORDS`
- Убрать `_select_best_fragment`, `_collect_subtree_in_sentence` целиком
- `__init__` получает `FragmentSelector`
- `_count_unknowns_in_fragment` **остаётся** в use case (нужен CEFRClassifier)
- Финальный рендер: `render_fragment(tokens, fragment_indices)` из `rendering.py`

### Скелет `FragmentSelector.select`

```python
class FragmentSelector:
    def __init__(self, config, sources, cleaner, scorer): ...

    def select(self, tokens, target_index, protected_indices, unknown_counter) -> list[int]:
        raw = self._step1_generate_candidates(tokens, target_index)
        cleaned = self._step2_clean_boundaries(tokens, raw, protected_indices)
        filtered = self._step3_filter_candidates(tokens, cleaned, target_index)
        if not filtered:
            return self._step6_fallback(tokens, target_index, protected_indices)
        scored = self._step4_score(tokens, filtered, unknown_counter)
        return self._step5_select_best(scored)
```

Шесть методов по 5-15 строк. Каждый — чистая функция, легко юнит-тестируется.

---

## Часть 3. Шаги миграции (behavior-preserving)

После каждого шага: `pytest backend/tests/integration/test_full_pipeline_marked_fragments.py -x` должен быть зелёным. Это страховой полис.

**Шаг A — инфраструктура без поведения.** Создать пустую папку `fragment_selection/`, перенести `render` → `rendering.py`, общие утилиты → `utils.py`. Обновить импорты. Тесты.

**Шаг B — `FragmentSelectionConfig` с дефолтами.** Создать с текущими значениями. `BoundaryCleaner` и `analyze_text` ссылаются на конфиг вместо модульных констант. Поведение не меняется. Тесты.

**Шаг C — `StripRule` как полиморфные классы.** По одному правилу из if-лестниц `_should_strip_*` в отдельный класс, регистрация в реестре. После каждого правила — тесты. **Критично сохранить порядок** правил из текущей if-цепочки, иначе поведение съедет.

**Шаг D — `CandidateSource` как полиморфные классы.** `ClauseFinder` → `VerbSubtreeSource`. Создать `AncestorChainSource`, `SentenceSource`, `LegacyExtractorSource`. Use case по-прежнему вызывает `_select_best_fragment`, но внутри уже цикл по `self._sources`. Тесты.

**Шаг E — `Scorer` extracted.** `DefaultScorer` с тем же tuple-based score. `unknown_counter` — параметр конструктора. Use case передаёт замыкание на `_count_unknowns_in_fragment`. Тесты.

**Шаг F — переезд в `FragmentSelector.select`.** Вырезать `_select_best_fragment` из use case, перенести в новый класс. Use case вызывает `selector.select(...)`. Wiring в `container.py`. Тесты.

**Шаг G — удалить легаси-заглушки.** Физически удалить `fragment_extractor.py`, `boundary_cleaner.py`, `clause_finder.py`. Обновить unit-тесты — только импорты, не _проверяемое поведение_. Регрессионный тест **не трогать**. Тесты.

**Шаг H — финальная проверка.** `pytest backend/tests -x`, `ruff check`, `mypy --strict`. Всё зелёное.

Каждый шаг — отдельный коммит `refactor: ...`. Если что-то краснеет — фикс в том же шаге.

---

## Часть 4. Trade-offs и red lines

**Делаем:**
- Включение/выключение правил и источников через `enabled_*` строковые списки
- Настройка весов скоринга тремя int'ами + `length_hard_cap`
- Реестр как `dict[str, ...]`, плоский

**Не делаем (overkill):**
- DI-контейнер поверх существующего `container.py` (`injector` и т.п.)
- YAML/JSON-конфиг — `FragmentSelectionConfig()` с дефолтами в коде хватит
- Абстрактные базовые классы вместо `typing.Protocol`
- Plug-in scoring — один `DefaultScorer`, заменить тривиально
- Класс `FragmentRenderer` — это просто функция
- **Переписывать тесты strip-правил** — они через публичный API, импорты подменим

**Риски:**
- **Порядок правил.** Текущая if-лестница проверяет правила сверху вниз и возвращает True у первого. После рефакторинга порядок задаётся `enabled_rules`. Перенос — по одному, после каждого тесты.
- **`LegacyExtractorSource` может оказаться мёртвым** (всегда хуже sentence + cleanup). Но требование «не ломать 20 кейсов» обязывает оставить. Почистить позже отдельной задачей.
- **`unknown_counter` callback — не утечка.** `FragmentSelector` принимает `Callable`, не знает про CEFR. Use case поставляет реализацию. Clean Architecture соблюдена.

**Объём:** ~+300 строк (много protocol-классов), ~-150 существующих (упрощённые BoundaryCleaner / FragmentExtractor / use case). Чистый прирост ~150 строк.

---

## Что НЕ входит в этот рефакторинг

- Wave 3+ (под-сегментация по запятым для оставшихся `conclusion`/`need`) — отдельная задача
- Спецрежимы для lyrics/субтитров — отдельная задача
- Замена `en_core_web_sm` на `_md`/`_trf` — отдельная задача
- LLM-fallback для сложных кейсов — отдельная задача

После рефакторинга всё это станет проще делать (новый источник кандидатов = новый класс + строка в конфиге), но это уже не часть этой задачи.
