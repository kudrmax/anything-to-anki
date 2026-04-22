# Unified Dictionary Data — Design Spec

**Дата:** 2026-04-23
**Задача:** Унифицировать словарные данные: разделить Cambridge JSON/DB на независимые источники (CEFR, IPA, audio, usage) с минимально необходимыми полями

---

## Цель

Проект не должен знать о конкретных словарях (Cambridge, Oxford и т.д.). Вместо этого — единый формат JSON-файлов для четырёх типов данных. Пользователь указывает папку со словарями в конфиге, проект читает файлы по фиксированной схеме.

---

## Три репозитория

### Репо 1: anything-to-anki (этот проект)

Потребитель словарей. Конфиг `DICTIONARIES_DIR` указывает на папку `unified/` из репо 3.

### Репо 2: dictionary-tools (public)

Код без данных:
- Скрейперы (Cambridge parser)
- Конвертеры (raw → unified) для всех источников
- Нормализация usage labels (логика из текущего `usage_groups.py` переезжает сюда)
- POS-маппинг из формата каждого источника → unified

```
dictionary-tools/
├── scrapers/
│   └── cambridge/
│       └── run_scrape.py
├── converters/
│   ├── cambridge_to_unified.py
│   ├── oxford_to_unified.py
│   ├── efllex_to_unified.py
│   └── kelly_to_unified.py
├── Makefile
└── README.md
```

### Репо 3: dictionaries (private)

Данные без кода:

```
dictionaries/
├── raw/
│   ├── cambridge.jsonl
│   ├── oxford5000.csv
│   ├── efllex.tsv
│   └── kelly.csv
├── unified/
│   ├── cefr/
│   │   ├── cambridge.json
│   │   ├── oxford.json
│   │   ├── efllex.json
│   │   └── kelly.json
│   ├── audio.json
│   ├── ipa.json
│   └── usage.json
└── README.md
```

---

## Unified JSON форматы

### CEFR (N файлов в `cefr/`, голосование)

```json
{
  "meta": {
    "name": "Oxford 5000",
    "priority": "high"
  },
  "entries": {
    "procrastinate": {
      "verb": {"B2": 1.0}
    },
    "abandon": {
      "verb": {"B2": 1.0},
      "noun": {"C1": 1.0}
    }
  }
}
```

Вероятностный источник (EFLLex):

```json
{
  "meta": {
    "name": "EFLLex",
    "priority": "normal"
  },
  "entries": {
    "procrastinate": {
      "verb": {"B1": 0.3, "B2": 0.5, "C1": 0.2}
    }
  }
}
```

- Ключ — лемма (lowercase)
- Значение — `{pos: {CEFRLevel: weight}}`
- POS в unified формате: `noun`, `verb`, `adjective`, `adverb`, `phrasal verb` и т.д.
- `meta.priority`: `"high"` или `"normal"`
- Веса — сырые частоты (не обязательно нормализованные, нормализация при сборке кэша)

### Audio (1 файл)

```json
{
  "procrastinate": {
    "us": "https://dictionary.cambridge.org/media/.../us_pron.mp3",
    "uk": "https://dictionary.cambridge.org/media/.../uk_pron.mp3"
  }
}
```

- Ключ — лемма (lowercase)
- `us`, `uk` — URL-ы. Оба опциональны.

### IPA (1 файл)

```json
{
  "procrastinate": {
    "us": "/proʊˈkræs.tɪ.neɪt/",
    "uk": "/prəˈkræs.tɪ.neɪt/"
  }
}
```

### Usage (1 файл)

```json
{
  "procrastinate": {
    "verb": ["disapproving"]
  },
  "gonna": {
    "verb": ["informal"]
  }
}
```

- Labels приходят нормализованные (конвертеры в репо 2 отвечают за нормализацию)
- Проект прокидывает labels as-is, без трансформации

---

## SQLite-кэш (dict.db)

JSON = source of truth. SQLite = рантайм-кэш. Генерируется в `{DICTIONARIES_DIR}/.cache/dict.db`.

### Почему не JSON в RAM

57K+ записей audio/IPA/usage — десятки MB в памяти. Предыдущий инцидент с OOM при загрузке 103MB подтверждает: читать через targeted SELECT безопаснее.

### Схема

```sql
CREATE TABLE cefr (
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    distribution TEXT NOT NULL,  -- JSON: {"B2": 1.0} или {"A1": 0.1, "B2": 0.5, "C1": 0.4}
    source_name TEXT NOT NULL,
    priority TEXT NOT NULL,      -- "high" / "normal"
    PRIMARY KEY (lemma, pos, source_name)
);

CREATE TABLE audio (
    lemma TEXT PRIMARY KEY,
    us_url TEXT,
    uk_url TEXT
);

CREATE TABLE ipa (
    lemma TEXT PRIMARY KEY,
    us_ipa TEXT,
    uk_ipa TEXT
);

CREATE TABLE usage (
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    labels TEXT NOT NULL,         -- JSON array: ["informal", "disapproving"]
    PRIMARY KEY (lemma, pos)
);

CREATE TABLE build_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- key="sources_hash" → SHA256 от всех JSON-файлов
-- key="built_at" → ISO timestamp
```

### Детекция изменений

Хэш содержимого (не mtime — ненадёжен при git clone/pull):

1. Собрать все JSON: `cefr/*.json` + `audio.json` + `ipa.json` + `usage.json`
2. SHA256 каждого файла
3. Отсортировать по имени, конкатенировать, SHA256 результата → `sources_hash`
4. Сравнить с `build_meta.sources_hash` в dict.db
5. Не совпадает или dict.db не существует → пересборка

### Пересборка

Всегда полная (partial update не стоит сложности для ~100K записей):

1. Прочитать все JSON, валидировать формат
2. Создать `dict.db.tmp` (атомарность)
3. Заполнить таблицы. Distribution в CEFR: нормализовать (freq / total)
4. Записать `sources_hash` в `build_meta`
5. `rename dict.db.tmp → dict.db` (атомарная замена)

### Валидация при сборке

- CEFR: обязательные `meta.name`, `meta.priority` (∈ {"high", "normal"}). Levels ∈ {A1–C2}. Distribution: значения ≥ 0, хотя бы одно > 0.
- Audio/IPA/Usage: корректный JSON, ожидаемая структура.
- При ошибке — понятное сообщение с именем файла и проблемой.

### Make-команды

```makefile
dict-rebuild:                    # Пересборка с нуля
    rm -f $(DICTIONARIES_DIR)/.cache/dict.db
    python -m backend.cli.build_dict_cache $(DICTIONARIES_DIR)

dict-update:                     # Пересборка если изменилось
    python -m backend.cli.build_dict_cache $(DICTIONARIES_DIR) --if-changed

up: dict-update                  # make up вызывает dict-update
    docker compose up -d --build
```

---

## Изменения в anything-to-anki

### Удаляется

- `infrastructure/adapters/cambridge/` — весь пакет (sqlite_reader, cefr_source, pronunciation_source, usage_lookup, usage_groups)
- `infrastructure/adapters/oxford_cefr_source.py`
- `infrastructure/adapters/efllex_cefr_source.py`
- `infrastructure/adapters/kelly_cefr_source.py`
- `dictionaries/cambridge.db`, `dictionaries/cambridge.jsonl`
- `dictionaries/cefr/oxford5000.csv`, `dictionaries/cefr/efllex.tsv`, `dictionaries/cefr/kelly.csv`
- `scripts/scrapers/cambridge/` (переезжает в репо 2)

### Остаётся

- `infrastructure/adapters/cefrpy_cefr_source.py` — встроенный fallback

### Добавляется

- `domain/ports/usage_source.py` — новый порт (ABC)
- `domain/services/pos_mapping.py` — конвертация spaCy POS (NN) → unified POS (noun) для lookup в dict.db
- `infrastructure/adapters/dict_cache/reader.py` — DictCacheReader, read-only SQLite к dict.db (singleton)
- `infrastructure/adapters/dict_cache/cefr_source.py` — реализует CEFRSource
- `infrastructure/adapters/dict_cache/pronunciation_source.py` — реализует PronunciationSource
- `infrastructure/adapters/dict_cache/usage_source.py` — реализует UsageSource (прокидывает labels as-is)
- `backend/src/backend/cli/build_dict_cache.py` — CLI для сборки dict.db
- `README.md` в DICTIONARIES_DIR — форматы, шаблоны, примеры для всех 4 типов

### Сборка в container.py

```python
dict_cache_path = Path(os.environ.get("DICTIONARIES_DIR", "dictionaries")) / ".cache" / "dict.db"
reader = DictCacheReader(dict_cache_path)

# CEFR: динамически из метаданных dict.db
cefr_sources, priority_sources = [], []
for meta in reader.get_cefr_sources():
    src = DictCacheCEFRSource(reader, meta["name"])
    (priority_sources if meta["priority"] == "high" else cefr_sources).append(src)
cefr_sources.append(CefrpyCEFRSource())  # fallback

classifier = VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources)

pronunciation_source = DictCachePronunciationSource(reader)
usage_source = DictCacheUsageSource(reader)
```

### VotingCEFRClassifier

Интерфейс не меняется. `resolve_cefr_level` — убрать хардкод `PRIORITY_SOURCE_NAMES = ["Oxford 5000", "Cambridge Dictionary"]`. Вместо этого: priority определяется тем, в какой список (sources vs priority_sources) попал источник при сборке в container.py.

### Graceful degradation

Если dict.db не существует:
- Warning в логи
- CEFR: только cefrpy (fallback)
- Audio/IPA/Usage: пустые ответы (None)

---

## Конвертеры (репо 2)

### cambridge_to_unified.py

Читает `raw/cambridge.jsonl`, генерирует 4 файла:
- `unified/cefr/cambridge.json` — lemma + POS → CEFR первого sense. Priority: high
- `unified/audio.json` — lemma → первый US/UK audio URL
- `unified/ipa.json` — lemma → первый US/UK IPA
- `unified/usage.json` — lemma + POS → нормализованные labels (логика из `usage_groups.py`)

### oxford_to_unified.py

Читает `raw/oxford5000.csv` → `unified/cefr/oxford.json`. Priority: high.

### efllex_to_unified.py

Читает `raw/efllex.tsv` → `unified/cefr/efllex.json`. Сырые частоты. Priority: normal.

### kelly_to_unified.py

Читает `raw/kelly.csv` → `unified/cefr/kelly.json`. Priority: normal.

Каждый конвертер приводит POS из формата своего источника → unified формат.

---

## README с форматами

Лежит в `DICTIONARIES_DIR/README.md`. Содержание:
1. Структура папки
2. Формат каждого типа (CEFR, Audio, IPA, Usage) с шаблонами
3. Объяснение priority и distribution
4. Пошаговая инструкция «как добавить свой словарь»
5. Пересборка кэша: `make dict-rebuild`, `make dict-update`
