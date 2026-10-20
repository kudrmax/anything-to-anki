# Update и Re-cut вместо Rebuild с галочкой

Решения Макса 20.10.2026.

## Проблема

Rebuild с галочкой «Also unreviewed cards» смешивает две разные работы:

- **разложить карточки по текущему знанию** — нужно часто, после каждой разметки, и ничего не должно терять;
- **заново нарезать фразы** — нужно редко, после смены алгоритма нарезки, и может терять генерацию, сделанную по старому тексту.

Галочка решает за пользователя, можно ли терять генерацию, и он не понимает, ставить ли её.

## Принцип

Две операции вместо одной, без галочки:

1. **Update** никогда не меняет текст фраз и ничего не теряет. Делает всё, что зависит от знания и уровня.
2. **Re-cut phrases** делает то же, что Update, и вдобавок режет фразы заново. Генерация, сделанная по старому тексту, сбрасывается.

## Термины

- **Фраза** — запись `phrases`: кусок текста источника с target'ом. У слова может быть несколько фраз.
- **Карточка** — фраза, которую показывает review (`shown_by` задан).
- **Место** — ключ фразы (`OccurrenceKey`): где в документе стоит target.
- **Нарезка** — границы фразы внутри предложения; анализ выбирает их по `FragmentScore`.
- **Защищённая фраза** — с выбором (Learn / Cloze / Known / Skip), в Anki или с работой пользователя (правка, ручной выбор, добавлена вручную): `is_protected`. Ни одна операция её не меняет и не удаляет.
- **Решённое слово** — `is_decided`. Его фразы ни одна операция не меняет, показ не трогает.
- **Слово выбыло** — анализ его больше не находит (повысился уровень, сменился порог частотности, поменялась логика отбора) и пользователь не отмечал его в другом источнике (`LemmaKnowledge.elsewhere is None`).
- **Генерация по тексту** — Polish, TTS фразы, media из видео (скриншот, клип). Сделана из точного текста фразы.
- **Генерация по месту** — Meaning (с переводом, синонимами, примерами). Объясняет target в этом месте документа.

## Update

Текст существующих фраз не меняется. Что делает:

1. **Новые слова.** Слово, которого в источнике не было, а анализ его теперь находит (ты убрал его из Known, понизил уровень, поменялась логика отбора), получает фразы во всех своих местах; одна из них становится карточкой.
2. **Новые места.** У существующего слова анализ нашёл место, где фразы ещё нет: добавляется фраза с нарезкой анализа.
3. **Выбывшие слова.** Незащищённые фразы выбывшего слова удаляются вместе со всей генерацией, задачи по ним отменяются. Слово удаляется, если его ничего не держит (`keeps_word`).
4. **Слово, отмеченное в другом источнике** (Known, Learn, Learning там). Не трогается: его карточка уже на лету показана как сделанная и стоит в Reviewed.
5. **Лучшее место.** Выбор (`select_phrases`) заново ищет лучшую фразу слова, и показ может перейти на другую фразу. Фразы сравниваются по их текущему тексту (см. «Оценка фразы»). Генерация старой фразы остаётся при ней: если та снова станет лучшей, карточка вернётся со своей генерацией.
6. **Секции.** Заработанная секция (Ready / Extra / Probably known) пересчитывается у всех фраз без выбора и не в Anki, как сейчас.
7. **Ключи.** Фраза, ключ которой сдвинулся внутри строки при том же тексте, получает новый ключ (`_moved_keys`), как сейчас.
8. **Место пропало, слово осталось.** Фраза остаётся как есть, и в выборе она участвует наравне с остальными.

## Re-cut phrases

Всё, что делает Update, и вдобавок:

9. **Новая нарезка.** Незащищённая фраза нерешённого слова, у которой анализ режет то же место иначе (другой текст), получает новый текст, а её revision растёт.
   - Сбрасывается генерация по тексту: Polish (вместе с отменённым), TTS, media. Таймкоды media ставятся по новому тексту.
   - Meaning остаётся.
   - Задачи в очереди переходят на новую revision и сработают по новому тексту (`_queued_jobs_follow`). Задачи, которые уже выполняются, отменяются.
10. **Место пропало, слово осталось.** Незащищённая фраза нерешённого слова удаляется вместе с генерацией; показ переходит по п. 5.

## Оценка фразы

Сейчас выбор сравнивает фразы по `fragment_score`, посчитанному при нарезке. В Update текст не меняется, а знание меняется, поэтому оценка фразы считается по её показанному тексту (Polish, если он показан):

- поля `length_overflow`, `incomplete`, `boundary_penalty`, `content_count` берутся из сохранённого `fragment_score`;
- поле `unknowns` считается заново: `len(new_words(shown_phrase, knowledge))`.

Функция в домене: `current_score(stored: float, unknowns: int) -> float`, она заменяет разряд `unknowns` в упакованном числе (`FragmentScore.as_number`). Выбор в обеих операциях ранжирует фразы по ней.

## Кто какую операцию запускает

| Кто запускает | Операция |
|---|---|
| Пункт меню источника или набора источников | Update или Re-cut phrases, на выбор пользователя |
| Смена уровня CEFR или настройки порога (`background_rebuild_launcher`) | Update |
| `make fix-sections` (`fix_sections`) | Update |
| Первая обработка источника (`process_source`) | Update (фраз ещё нет, результат тот же, что сейчас) |

У источников без своего текста (тема, Saved phrases) есть только Update; он пересчитывает секции (`plan_sections`), как сейчас Rebuild. Re-cut им не предлагается.

## Модель

**Домен:**
- `RebuildMode(StrEnum)`: `UPDATE`, `RECUT` — в `domain/value_objects`.
- `plan_rebuild(..., mode, done_elsewhere: frozenset[str])` вместо `include_open`. `done_elsewhere` — леммы, отмеченные в другом источнике (п. 4).
- `_Planner._phrase`: правило по п. 3, 4, 8–10 вместо пары «touched / include_open». `is_touched` удаляется.
- `OccurrenceTextUpdate.reset_results` → `drop_text_results`: удаляет Polish, TTS и media, оставляет Meaning.
- `phrase_selection.is_frozen(o, include_open)` → `is_frozen(o)`: только защищённая фраза. `select_phrases` ранжирует по `current_score`.
- `OccurrenceRow` получает `has_polish: bool` (`polished_phrase` задан, отменён или нет), `has_meaning: bool`, `has_text_media: bool` (TTS или media с файлом) для счётчиков.
- `SourceOperationKind.RECUT`; `available_operations` для источника со своим текстом → `(REBUILD, RECUT)`. `REBUILD` в UI называется Update.

**Счётчики (`RebuildCounts`)**, каждый — по фразам плана:
- `words_added` — новые слова (п. 1);
- `words_removed` — выбывшие слова, которые удаляются (п. 3);
- `cards_lost_generation` — удаляемые фразы с `has_polish` или `has_meaning` (п. 3, 10);
- `cards_moved` — карточки, показ которых перешёл на фразу без генерации (п. 5);
- `cards_recut` — фразы с новым текстом (п. 9);
- `cards_recut_lost_polish` — из них с `has_polish` или `has_text_media`;
- `nothing_to_update` — план пуст.

`cards_new_phrase`, `cards_text_reset`, `cards_without_generation` удаляются.

**Application:**
- `RebuildRequest.include_open` → `mode: RebuildMode`.
- `SourceRebuilder.plan/apply(analysed, mode)`; `analyse` собирает `done_elsewhere` из `UserVocabulary`.
- `RebuildSourceUseCase`, `ScopeOperationUseCase.rebuild/preview` принимают `mode`.
- `RebuildPreviewDTO` → одно поле `counts`; `RebuildSummaryDTO.include_open` → `mode`.

**API:** `POST /api/operations/rebuild/preview?scope=&mode=` и `POST /api/operations/rebuild?scope=` с телом `{mode}`.

**Frontend:**
- `client.ts`: `previewRebuild(scope, mode)`, `rebuild(scope, mode)`; `types.ts` — новые DTO.
- В меню источника и набора — два пункта: **Update** и **Re-cut phrases** (второй — только если backend его предлагает).
- `RebuildDialog` получает `mode`, галочки нет. Тексты:

| Место | Update | Re-cut phrases |
|---|---|---|
| Заголовок | `Update “X”` | `Re-cut phrases of “X”` |
| До превью | `Finds new words, removes words you no longer need and moves cards to simpler sentences. Phrase texts and their Polish, Meaning and audio stay.` | `Also cuts every phrase again by the current logic. A phrase that changes loses its Polish, audio and video; Meaning stays.` |
| Превью и итог | `N new words, M words removed` | то же |
| | `K of the removed cards had Polish or Meaning` (если > 0) | то же |
| | `N cards move to a simpler sentence — need ✨ there` (если > 0) | то же |
| | — | `N phrases get a new cut, K of them lose Polish or audio` (если > 0) |
| Пустой план | `Already up to date` + только Close | то же |

Сноска `The numbers may differ slightly from the result.` — только при непустом превью.

## Миграции

Нет: схема не меняется.

## Риски

- После Re-cut Meaning объясняет target по старому тексту (`context=` в промпте). Если фраза стала короче, в объяснении может упоминаться то, чего во фразе уже нет.

## Тесты

- Update: новое слово → фразы во всех местах, одна показана; новое место → новая фраза; выбывшее слово с Polish, Meaning и TTS → удалено, задачи отменены, защищённая фраза того же слова осталась; слово Known в другом источнике → не тронуто.
- Update: ни у одной фразы не меняются текст, Polish, Meaning, TTS, media; другая нарезка анализа игнорируется.
- Update: выучил слова → показ переходит на фразу, где по `current_score` меньше незнакомых; старая фраза сохранила генерацию; решённое слово не меняется.
- Re-cut: новая нарезка → текст новый, revision + 1, Polish (и отменённый), TTS, media удалены, Meaning на месте, таймкоды новые; задача в очереди перешла на новую revision, выполняющаяся отменена.
- Re-cut: место пропало → фраза удалена с генерацией, показ перешёл.
- Защищённые фразы и решённые слова: ни одна операция их не меняет.
- Тема и Saved phrases: только Update, меняет только секции.
- Смена уровня и `fix_sections` запускают Update.
- Счётчики превью совпадают с итогом на том же состоянии; пустой план → `nothing_to_update`.
