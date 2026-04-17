# Cambridge CEFR Source — дизайн

## Проблема

Voting CEFR Classifier использует 4 источника (cefrpy, EFLLex, Oxford 5000, Kelly) с равными весами. Все они — производные датасеты: частотные списки, автоматические классификации, академические корпуса. Cambridge Dictionary — живой редакторский словарь с CEFR-разметкой на ~27% sense'ов — самый авторитетный источник, но не используется.

## Решение

Добавить Cambridge как **приоритетный** источник CEFR. Если Cambridge знает слово — его ответ финальный, голосование не нужно. Если не знает — fallback на голосование текущих 4-х источников.

Параллельно: создать универсальный парсер `cambridge.jsonl`, который загружает данные в типизированные dataclasses. Сейчас из парсера используется только CEFR, но архитектура закладывается под расширение (audio, IPA, usages, domains — задачи 1, 3, 4, 6 из `tasks_cambridge.md`).

## Решения, принятые при брейншторме

| Вопрос | Решение | Альтернативы |
|---|---|---|
| Агрегация CEFR по sense'ам | Медиана уровней | Частотное распределение, минимум |
| Веса в classifier | Cambridge-first (приоритет, не голосование) | Равные 1/5, повышенный вес Cambridge |
| POS-маппинг | Penn Treebank → Cambridge с fallback на все POS | Строгий без fallback |
| Загрузка данных | Eager load в dict при старте | SQLite-индекс |
| Расположение парсера | `infrastructure/adapters/cambridge/` | Domain value objects |
| Разделение данных между адаптерами | Контейнер парсит один раз, передаёт dict в адаптеры | Каждый адаптер парсит сам |

## Архитектура

### Парсер cambridge.jsonl

**Расположение:** `infrastructure/adapters/cambridge/`

**Модели (`models.py`):**

```python
@dataclass(frozen=True)
class CambridgeSense:
    definition: str
    level: str            # "A1", "B2", "" (пустая строка если нет)
    examples: list[str]
    usages: list[str]
    domains: list[str]
    regions: list[str]
    image_link: str

@dataclass(frozen=True)
class CambridgeEntry:
    headword: str
    pos: list[str]        # ["noun"], ["verb"], ["phrasal verb"]
    uk_ipa: list[str]
    us_ipa: list[str]
    uk_audio: list[str]
    us_audio: list[str]
    senses: list[CambridgeSense]

@dataclass(frozen=True)
class CambridgeWord:
    word: str
    entries: list[CambridgeEntry]
```

Dataclasses повторяют структуру JSON. Все поля присутствуют — парсер не фильтрует, полная информация доступна любому будущему потребителю.

**Парсер (`parser.py`):**

```python
def parse_cambridge_jsonl(path: Path) -> dict[str, CambridgeWord]:
    """Читает cambridge.jsonl, возвращает dict по headword.
    
    Если файл отсутствует — логирует warning, возвращает пустой dict.
    Битые строки — логирует warning, пропускает.
    """
```

- Чистый маппинг JSON → dataclasses, никакой бизнес-логики
- Отсутствие файла → пустой dict + warning в лог
- Битая JSON-строка → пропустить + warning в лог
- Результат: `dict[str, CambridgeWord]` с ключом по `word`

### CambridgeCEFRSource

**Расположение:** `infrastructure/adapters/cambridge/cefr_source.py`

Реализует порт `CEFRSource`.

**Конструктор:** принимает `dict[str, CambridgeWord]` (не путь к файлу — парсинг делает контейнер).

**POS-маппинг Penn Treebank → Cambridge:**

| Penn Treebank | Cambridge |
|---|---|
| NN, NNS, NNP, NNPS | noun |
| VB, VBD, VBG, VBN, VBP, VBZ | verb |
| JJ, JJR, JJS | adjective |
| RB, RBR, RBS | adverb |
| UH | exclamation |
| MD | modal verb |
| IN | preposition |
| DT | determiner |
| PRP, PRP$ | pronoun |
| CC | conjunction |

**Алгоритм `get_distribution(lemma, pos_tag)`:**

1. Найти `CambridgeWord` по `lemma`
2. Отфильтровать entries по mapped POS (если есть совпадение)
3. Если нет совпадений по POS → взять все entries (fallback)
4. Собрать все `sense.level` из отфильтрованных entries, игнорируя пустые строки
5. Если ни одного level → `{CEFRLevel.UNKNOWN: 1.0}`
6. Вычислить медиану levels → `{median_level: 1.0}`

**Медиана:** уровни сортируются по порядку (A1=1, A2=2, B1=3, B2=4, C1=5, C2=6). Для чётного количества — нижний из двух средних (округление вниз, в пользу более лёгкого уровня).

### Изменения в VotingCEFRClassifier

**Текущая сигнатура:**
```python
class VotingCEFRClassifier(CEFRClassifier):
    def __init__(self, sources: list[CEFRSource]) -> None:
```

**Новая сигнатура:**
```python
class VotingCEFRClassifier(CEFRClassifier):
    def __init__(
        self,
        sources: list[CEFRSource],
        priority_source: CEFRSource | None = None,
    ) -> None:
```

**Новая логика `classify()`:**
1. Если `priority_source` задан → вызвать `priority_source.get_distribution(lemma, pos_tag)`
2. Если результат не `{UNKNOWN: 1.0}` → вернуть уровень с max probability (это финальный ответ)
3. Иначе → голосование по `sources` с равными весами (1/N), как сейчас

`priority_source` не входит в `sources` — если Cambridge не знает слово, он не участвует в голосовании.

### DI (container.py)

```python
# Парсим Cambridge один раз
cambridge_path = project_root / "dictionaries" / "cambridge.jsonl"
cambridge_data = parse_cambridge_jsonl(cambridge_path)

# CEFR sources
cambridge_cefr = CambridgeCEFRSource(cambridge_data)
cefr_data_dir = project_root / "dictionaries" / "cefr"
cefr_sources: list[CEFRSource] = [
    CefrpyCEFRSource(),
    EFLLexCEFRSource(cefr_data_dir / "efllex.tsv"),
    OxfordCEFRSource(cefr_data_dir / "oxford5000.csv"),
    KellyCEFRSource(cefr_data_dir / "kelly.csv"),
]
self._cefr_classifier = VotingCEFRClassifier(cefr_sources, priority_source=cambridge_cefr)
```

`cambridge_data` сохраняется в контейнере для передачи будущим адаптерам (audio, IPA и т.д.).

### Graceful degradation

Если `cambridge.jsonl` отсутствует:
1. Парсер возвращает пустой dict
2. `CambridgeCEFRSource` на любой запрос отвечает `{UNKNOWN: 1.0}`
3. `VotingCEFRClassifier` всегда уходит в fallback на 4 источника
4. Система работает ровно как до этих изменений

## Тесты

### Формат JSONL
- Тест читает реальный `cambridge.jsonl`, берёт N случайных записей
- Валидирует структуру: обязательные поля (`word`, `entries`), типы значений
- Проверяет формат CEFR levels: пустая строка или одно из A1/A2/B1/B2/C1/C2
- Проверяет формат POS: непустой список строк в каждом entry
- **Цель:** если скрапер перегенерирует JSONL со сломанной структурой — тест упадёт

### Парсер
- Корректный парсинг: несколько записей → правильные dataclasses
- Отсутствующий файл → пустой dict, без исключений
- Битая JSON-строка → пропущена, остальные распарсены
- Пустой файл → пустой dict

### CambridgeCEFRSource
- Медиана из нескольких sense'ов: [A1, A1, B1] → A1; [A1, B2, C1] → B2
- POS-маппинг: запрос с VB → фильтрация по verb entries
- POS fallback: запрос с неизвестным POS → все entries
- Слово без CEFR-разметки → UNKNOWN
- Слово отсутствует → UNKNOWN

### VotingCEFRClassifier (Cambridge-first)
- Cambridge знает слово → его ответ, голосование не вызывается
- Cambridge не знает → fallback на голосование 4-х источников
- `priority_source=None` → работает как раньше (обратная совместимость)

## Файловая структура изменений

```
backend/src/backend/infrastructure/adapters/cambridge/
├── __init__.py
├── models.py          # CambridgeWord, CambridgeEntry, CambridgeSense
├── parser.py          # parse_cambridge_jsonl()
└── cefr_source.py     # CambridgeCEFRSource

backend/src/backend/domain/services/
└── voting_cefr_classifier.py   # + priority_source параметр

backend/src/backend/infrastructure/
└── container.py                # + Cambridge парсинг и wiring

backend/tests/
├── test_cambridge_jsonl_format.py    # валидация формата реального файла
├── test_cambridge_parser.py          # unit-тесты парсера
├── test_cambridge_cefr_source.py     # unit-тесты адаптера
└── test_voting_cefr_classifier.py    # обновить: Cambridge-first логика
```
