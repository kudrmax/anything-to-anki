# Unified Dictionary Data

Эта папка содержит словарные данные в unified JSON формате. Проект читает их через SQLite-кэш (`.cache/dict.db`), который собирается автоматически при `make up`.

## Быстрый старт

### 1. Подготовить словари

Подготовьте JSON-файлы в формате, описанном ниже. Для генерации из открытых источников (Cambridge, Oxford 5000, EFLLex, Kelly) используйте конвертеры из [anything-to-anki-parsers](https://github.com/kudrmax/anything-to-anki-parsers).

### 2. Разместить файлы

**Вариант A:** положите файлы прямо в эту папку (`dictionaries/`).

**Вариант B:** храните файлы в отдельной папке и укажите путь в `.env`:

```bash
DICTIONARIES_DIR=/path/to/your/dictionaries
```

### 3. Собрать кэш и запустить

```bash
make up    # автоматически вызовет dict-update → соберёт .cache/dict.db
```

Если вы обновили JSON-файлы:

```bash
make dict-rebuild   # пересборка кэша с нуля
make up
```

---

## Структура

```
dictionaries/
├── cefr/               # N файлов, голосование между ними
│   ├── oxford.json
│   ├── cambridge.json
│   └── efllex.json
├── audio.json          # один файл
├── ipa.json            # один файл
├── usage.json          # один файл
├── .cache/             # автогенерируемый кэш (в .gitignore)
│   └── dict.db
└── README.md
```

## Форматы

### CEFR (N файлов в `cefr/`)

Каждый файл — один источник CEFR-уровней. Проект голосует между всеми источниками.

```json
{
  "meta": {
    "name": "My Dictionary",
    "priority": "normal"
  },
  "entries": {
    "example": {
      "noun": {"B1": 1.0}
    },
    "run": {
      "verb": {"A2": 3.0, "B1": 7.0}
    }
  }
}
```

**Поля:**
- `meta.name` — название источника (произвольная строка)
- `meta.priority` — `"high"` или `"normal"`. Источники с `"high"` проверяются первыми; если хотя бы один знает слово, голосование не запускается
- `entries` — ключ: лемма (lowercase), значение: `{pos: {CEFRLevel: weight}}`
- POS в unified формате: `noun`, `verb`, `adjective`, `adverb`, `phrasal verb`, `exclamation`, `modal verb`, `preposition`, `determiner`, `pronoun`, `conjunction`
- CEFRLevel: `A1`, `A2`, `B1`, `B2`, `C1`, `C2`
- Weights — сырые частоты, не обязательно нормализованные. Нормализация происходит при сборке кэша
- Для однозначных источников: `{"B2": 1.0}`
- Для вероятностных: `{"A2": 3.0, "B1": 7.0}` (будет нормализовано в `{"A2": 0.3, "B1": 0.7}`)

### Audio (1 файл `audio.json`)

```json
{
  "example": {
    "us": "https://example.com/us_pron.mp3",
    "uk": "https://example.com/uk_pron.mp3"
  }
}
```

- Ключ: лемма (lowercase)
- `us`, `uk` — URL-ы аудиофайлов. Оба опциональны

### IPA (1 файл `ipa.json`)

```json
{
  "example": {
    "us": "/ɪɡˈzæm.pəl/",
    "uk": "/ɪɡˈzɑːm.pəl/"
  }
}
```

- Ключ: лемма (lowercase)
- `us`, `uk` — IPA транскрипции. Оба опциональны

### Usage (1 файл `usage.json`)

```json
{
  "example": {
    "noun": ["formal"]
  },
  "gonna": {
    "verb": ["informal"]
  }
}
```

- Ключ: лемма (lowercase)
- Значение: `{pos: [labels]}`. Labels — произвольные строки, проект не трансформирует их

## Как добавить свой словарь

1. Для CEFR: создайте JSON-файл в формате выше и положите в `cefr/`
2. Для Audio/IPA/Usage: добавьте записи в соответствующий файл
3. Пересоберите кэш: `make dict-rebuild`

## Управление кэшем

```bash
make dict-update    # пересобрать если JSON изменились
make dict-rebuild   # пересобрать с нуля
```

`make up` автоматически вызывает `make dict-update`.
