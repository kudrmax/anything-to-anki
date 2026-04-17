# Cambridge Dictionary — задачи интеграции

Источник: `dictionaries/cambridge.jsonl` (103 MB, JSONL, ~130K headwords, ~200K senses).
Структура: word → entries[] (headword + pos + IPA + audio) → senses[] (definition, CEFR level, examples, usages, domains, regions, image_link).

---

## Задачи

### 1. Audio на карточках

**Контекст:** Cambridge имеет готовые mp3-ссылки (UK + US) на 92.9% headwords. Аудио привязано к headword, не к sense — одно произношение на все значения. US покрытие лучше (92.9%) чем UK (68.7%). Ссылки ведут на Cambridge CDN (`dictionary.cambridge.org/media/english/...`).

**Что сделать:** подтягивать аудио-ссылку из Cambridge при генерации карточки. Если для target есть аудио — добавлять на карточку (скачивать mp3 и прикладывать в Anki media, либо использовать URL напрямую — уточнить что поддерживает AnkiConnect).

**Открытые вопросы:**
- UK или US или оба? (US покрытие выше)
- Скачивать mp3 локально или ссылка?
- Куда в шаблоне карточки ставить аудио?

---

### 2. CEFR как 5-й источник в voting classifier

**Контекст:** Сейчас 4 источника (cefrpy, EFLLex, Oxford 5000, Kelly) голосуют с равным весом 1/4. Каждый возвращает distribution по уровням; если источник не знает слово — возвращает `{UNKNOWN: 1.0}`. Cambridge имеет CEFR-разметку на ~27% sense'ов (A1-C2), привязанную к конкретному sense, а не к слову целиком.

**Что сделать:** создать `CambridgeCEFRSource`, реализующий порт `CEFRSource`. Логика: по lemma+POS найти все sense'ы с непустым `level`, взять **медиану** уровней. Sense'ы без CEFR — игнорировать. Если ни один sense не размечен — вернуть `{UNKNOWN: 1.0}`. Добавить как 5-й источник в `VotingCEFRClassifier` (вес станет 1/5 = 0.20).

**Детали:** classifier живёт в `domain/services/voting_cefr_classifier.py`, порт `CEFRSource` — в `domain/ports/cefr_source.py`. Новый адаптер — в `infrastructure/adapters/`.

**Продумать: пересмотр весов в voting classifier.** Сейчас все источники равновесные (1/N). Но Cambridge — самый полный и авторитетный словарь, ему можно доверять больше остальных. Равный вес с cefrpy/Kelly/EFLLex/Oxford несправедлив. Нужно продумать схему весов: возможно Cambridge получает больший вес, или при наличии Cambridge-ответа другие источники понижаются, или вообще Cambridge приоритетный (если он знает — его ответ, если нет — голосование остальных). Решить при реализации.

---

### 3. Usages как критерий отбора target'ов

**Контекст:** CEFR отвечает на вопрос "какого уровня слово?" — чтобы выбирать слова под уровень человека. Usages — дополнительное измерение: "какого рода это слово?" — чтобы отбирать наиболее полезные слова из подходящих по уровню.

Cambridge содержит ~30K sense'ов с usage-разметкой. Usages группируются в 6 значимых категорий:

| Группа | Usages | Кол-во |
|--------|--------|--------|
| Регистр речи | informal, very informal, slang, infml | ~10 400 |
| Формальность | formal, fml | ~6 800 |
| Устаревшее | old-fashioned, old use, dated | ~2 200 |
| Коннотация | disapproving, approving, humorous | ~3 600 |
| Специализированное | specialized, specialist | ~7 300 |
| Оскорбительное | offensive, very/extremely offensive | ~590 |

(Мелкие группы: literary ~1300, trademark ~290, child's word ~70, not standard ~70, figurative ~3)

Есть дубли/опечатки в данных (infml=informal, fml=formal, specalized=specialized) — нормализовать при загрузке.

**Что сделать:** использовать usages как дополнительный сигнал при ранжировании target'ов. Продумать: какие usages повышают/понижают приоритет слова, как это сочетается с CEFR и frequency при сортировке кандидатов.

**Примечание:** usages и CEFR почти не пересекаются (96% usages на sense'ах без CEFR) — это именно дополнительное измерение, не дублирующее.

---

### 5. Обогатить словарь phrasal verbs и multi-word verbs из Cambridge

**Контекст:** Текущий `phrasal_verbs.json` — плоский список из 3 361 записи без CEFR и определений. Cambridge содержит:
- 225 headwords с `pos=phrasal verb` (134 отсутствуют в текущем словаре)
- 1 149 headwords с `pos=verb` и multi-word (`get to know` [B1], `would like` [A1], `come to do something` [C2])
- CEFR-разметку для части из них
- Definitions и examples для каждого

**Что сделать (одна задача, три действия):**
1. Расширить `phrasal_verbs.json` — добавить 134 phrasal verbs из Cambridge, которых нет в текущем списке
2. Добавить CEFR-уровень к записям — текущий словарь без уровней, Cambridge даёт CEFR для части phrasal verbs. Формат словаря нужно будет расширить (из плоского списка строк в структуру с level)
3. Добавить 1 149 verb multi-words — ��олее широкая категория чем phrasal verbs (`get to know`, `would like`, `be going to` и т.д.), тоже с CEFR где есть

**Детали:** словарь живёт в `infrastructure/adapters/phrasal_verbs.json`, порт — `domain/ports/phrasal_verb_dictionary.py`, детектор — `domain/services/phrasal_verb_detector.py`. Формат словаря изменится — нужно обновить адаптер и, возможно, порт.

---

### 6. Domains как критерий приоритизации target'ов

**Контекст:** Cambridge размечает ~21K sense'ов по предметным доменам (FINANCE, medical, LAW, IT, biology, chemistry, STOCK MARKET и т.д. — всего ~90 доменов с дублями/опечатками). Domains и CEFR почти не пересекаются (99.4% domains на sense'ах без CEFR).

**Что сделать:**
1. Хранить domain как атрибут слова/sense — нормализовать дубли при загрузке (LAW/law, FINANCE/finance, medical/medicine и т.д.)
2. Ввести приоритеты для доменов — аналогично тому как CEFR определяет "подходит ли слово по уровню", domain определяет "подходит ли слово по тематике". Например, для general English слова без домена или из общих доменов (business, politics) приоритетнее, чем из узких (STOCK MARKET, chemistry, trigonometry)
3. Продумать: пользовательская настройка приоритетов доменов (человек может учить medical English — тогда medical домен наоборот приоритетный)

---

### 4. IPA из Cambridge с fallback на AI

**Контекст:** Сейчас IPA генерируется AI в составе `CandidateMeaning`. Cambridge даёт готовую IPA на 93% headwords (UK + US варианты отдельно, иногда несколько вариантов произношения). IPA — детерминированная вещь, AI может галлюцинировать.

**Что сделать:** добавить выбор источника IPA — Cambridge или AI. Если Cambridge знает слово — берём оттуда. Если нет (7% headwords) — fallback на AI-генерацию как сейчас.
