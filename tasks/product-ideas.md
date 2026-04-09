# Продуктовые идеи (брейншторм)

Состояние кода проверено по факту, не по слухам. Каждый пункт помечен: ✅ уже есть / 🟡 частично / ❌ нет.

---

## Уже реализовано (снято из брейншторма)

- ✅ **Phrasal verbs** — `backend/src/backend/domain/services/phrasal_verb_detector.py`, два слоя (dep=prt + dep=prep по словарю)
- ✅ **Длина/качество фрагмента (базово)** — `FragmentExtractor` с dep-парсингом, `MIN_FRAGMENT_WORDS=5`, эскалация subtree → head → sentence → trim. **Качество границ всё равно недостаточное — отдельный документ `fragment-boundaries.md`**
- ✅ **Фильтр proper nouns** — `CandidateFilter.is_relevant_token` отсекает `is_propn`. Дыра только с нестандартными формами (`Rickless`, `Mortys`), которые spaCy не распознаёт как PROPN
- ✅ **Аудио из оригинала** — `MediaExtractor.extract_audio` извлекает аудио-клип ±N ms вокруг фразы → `CandidateMedia.audio_path` → Anki field "Audio". TTS не используется
- ✅ **Скриншот в карточке** — `extract_screenshot` → WebP на таймкоде → Anki field "Image". Полноценный видео-клип не делается (Anki не поддерживает inline-видео нормально)
- ✅ **Word families на уровне леммы** — `AnalyzeTextUseCase` группирует по `(lemma, pos)`. Ограничение: `decide` (VERB) и `decision` (NOUN) — разные записи в whitelist
- ✅ **AI-генерация back of card** — `GenerateMeaningUseCase` + `config/prompts.yaml`: meaning, translation, synonyms, IPA. Mnemonic нет
- ✅ **Метрика «чистоты» фрагмента считается** — `fragment_unknown_count` в `analyze_text.py:146`. Фрагмент помечается clean/dirty (<2 unknown слов). НО: сейчас не используется для выбора лучшей фразы — см. п.1 ниже
- ✅ **Manual candidate addition** — `AddManualCandidateUseCase`, спека от 2026-04-05. Закрывает коллокации руками (escape-hatch)

---

## Топ-блок: главные продуктовые рычаги

### 1. Выбор лучшей фразы для target'а (САМЫЙ ДЕШЁВЫЙ И ЦЕННЫЙ)

**Самый дешёвый и самый ценный пункт во всём списке.** Метрика `fragment_unknown_count` уже считается, но pipeline берёт **первую найденную** фразу, а не минимум по `unknown_count`. Инфраструктура для «target — единственный незнакомый элемент» уже есть, но не используется для отбора.

**Что делать:** при дедупликации кандидатов по `(lemma, pos)` оставлять не первое вхождение, а фразу с минимальным `fragment_unknown_count` (тай-брейкер — длина в sweet spot).

**Файлы:** `backend/src/backend/application/use_cases/analyze_text.py:64-94` (метод группировки кандидатов).

**Эффект:** прямое попадание в центральное обещание из CLAUDE.md, ~20 строк кода, видно сразу.

---

### 2. Импорт известных слов из Anki

Сейчас `ManageKnownWordsUseCase` умеет только `list_all` и `delete`. Нет use case'а, который через AnkiConnect (`findCards` + `cardsInfo`) вытащит существующие карточки и засеет whitelist.

**Почему критично:** новый пользователь получает 80% «известного мусора» в первой же сессии — блокирующий UX. Также фундамент для:
- адаптивного CEFR (п.9)
- более точного `fragment_unknown_count` → улучшает п.1
- feedback loop из Anki (п.12)

**Что есть в коде:** AnkiConnect-адаптер уже используется для push (`SyncToAnkiUseCase`). Нужен симметричный reader.

**Что нужно:** один use case + endpoint + кнопка «Импорт из Anki» в settings.

**Файлы:** `backend/src/backend/application/use_cases/manage_known_words.py:11-30`.

---

### 3. YouTube как источник

`SourceType` поддерживает только TEXT/LYRICS/SUBTITLES/VIDEO (локальные файлы). YouTube — самый частый сценарий для learners, и его нет вообще.

**Что делать:** добавить SourceType.YOUTUBE, использовать `yt-dlp` (даёт субтитры, аудио, метаданные одной командой). Архитектура к этому готова (есть VIDEO-парсер).

**Эффект:** расширяет аудиторию сильнее всего остального.

**Файлы:** `backend/src/backend/domain/value_objects/source_type.py:6-10`.

---

### 4. Коллокации (ADJ+NOUN, VERB+dobj)

Phrasal verbs закрыты, коллокации (`make a decision`, `strong coffee`, `take advantage`) — нет. `WordCandidate` уже имеет `surface_form: str | None` для multi-word target'ов.

**Что делать:** детектор через dep-парсинг (`amod`, `dobj`) + словарь типичных коллокаций (BNC top-N). Архитектурно лежит ровно туда же, куда `phrasal_verb_detector`.

**Не критически блокирующий** — есть ручной escape-hatch через `AddManualCandidateUseCase`.

**Файлы:** новый `backend/src/backend/domain/services/collocation_detector.py` по образцу `phrasal_verb_detector.py`.

---

## Среднеценные

### 5. Верхняя граница Zipf

`FrequencyBand` имеет только `SWEET_SPOT_MIN/MAX = 3.0/4.5`, но `is_above_user_level` пропускает кандидатов и за пределами sweet spot. Слишком частые слова (`cause`, `cast`, `campaign` — Zipf > 5.0) лезут в результаты только из-за CEFR.

**Что делать:** добавить hard cap в `CandidateFilter` (например, Zipf > 5.5 → drop).

**Файлы:** `backend/src/backend/value_objects/frequency_band.py:5-6`, `backend/src/backend/infrastructure/adapters/wordfreq_frequency_provider.py`.

**Эффект:** три строки кода, заметно чище кандидаты.

---

### 6. Bulk actions + горячие клавиши в Review

`ReviewPage.tsx` — только клик-по-карточке, нет shortcut'ов (y/n/skip), нет multi-select. Прохождение 200 кандидатов сейчас — занудство.

**Особенно важно** в связке с п.2 (после массового импорта из Anki останутся «полузнакомые» — нужно быстро их разметить).

**Файлы:** `frontends/web/src/pages/ReviewPage.tsx:159-187`.

---

### 7. Whisper / транскрипция

Подкасты, аудиокниги, видео без субтитров — никак. Локальный `whisper.cpp` / `faster-whisper` решает.

**Стоимость:** большая работа, открывает большой пласт контента.

---

### 8. EPUB / PDF / web-статьи

В `InboxPage` уже есть UI-hint про «Article · html» / «Book · epub», но backend не парсит. Парсеры дешёвые (`ebooklib`, `pypdf`, `readability-lxml`), архитектура к ним готова.

**Файлы:** `frontends/web/src/pages/InboxPage.tsx:10-19` (hint уже есть), `backend/src/backend/domain/value_objects/source_type.py` (добавить типы).

---

### 9. Адаптивный CEFR

Сейчас уровень руками в settings. После п.2 (импорт из Anki) можно выводить уровень из распределения CEFR известных слов — никакого ML, чистая статистика.

**Файлы:** `backend/src/backend/application/use_cases/manage_settings.py:25-40`.

---

## Низкоприоритетное / спорное

### 10. Стоп-лист вульгарного/разговорного

Отсутствует. Но решается п.6 (bulk-skip) — пусть пользователь сам выкидывает за один раз.

### 11. Onboarding

Нет welcome-флоу. Имеет смысл только если п.2+п.3 закроют — иначе onboard'ить некуда.

### 12. Anki feedback loop (читать lapses из Anki)

Идея красивая, но дорогая и без явного user-pain'а сейчас. Использует тот же `AnkiConnectReader`, что и п.2 — если делается один раз, то под обе фичи.

### 13. Multi-language

Английский захардкожен везде (`zipf_frequency(..., "en")`, `en_core_web_sm`, prompts). Большая работа, и пока непонятно, есть ли спрос. Откладывать до явного запроса.

---

## Технические наблюдения (не идеи, а контекст)

- **Anki-интеграция полностью однонаправленная.** Push есть, pull нет. Блокирует п.2 и п.12 — обе требуют `AnkiConnectReader` адаптера. Реализовать один раз под обе фичи.
- **Field mapping в settings уже есть.** `manage_settings.py` умеет настраивать имена Anki-полей → архитектура к гибкости готова.
- **Нет retry logic в arq-jobs.** Если AI-генерация или ffmpeg-extract упадёт — кандидат остаётся в `failed`, ручное вмешательство. Связано с задачей по логированию из `TASKS.md`.

---

## Если выбирать одно — что брать первым

**П.1 (выбор лучшей фразы по `fragment_unknown_count`).**

- Прямое попадание в центральное обещание продукта из CLAUDE.md
- Метрика уже считается, инфраструктура есть
- Один файл, ~20 строк кода
- Эффект сразу виден

Сразу за ним — **п.2 (импорт из Anki)** как фундамент для всего остального.

Параллельно — **проблема качества границ фрагмента** (см. `fragment-boundaries.md`), потому что даже идеальный отбор фраз будет плох, если границы корявые.
