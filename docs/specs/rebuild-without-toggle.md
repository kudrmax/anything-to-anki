# Update и Re-cut вместо Rebuild с галочкой

Решения Макса 20.10.2026.

## Проблема

Rebuild с галочкой «Also unreviewed cards» смешивает две разные работы:

- **разложить карточки по текущему знанию** — нужно часто, после каждой разметки, и ничего не должно терять;
- **заново нарезать фразы** — нужно редко, после смены алгоритма нарезки, и может терять генерацию, сделанную по старому тексту.

Галочка решает за пользователя, можно ли терять генерацию, и он не понимает, ставить ли её.

## Принцип

Две операции вместо одной, без галочки:

1. **Update** никогда не меняет текст фраз и не теряет генерацию нужных слов. Делает всё, что зависит от знания и уровня.
2. **Re-cut phrases** делает то же, что Update, и вдобавок режет фразы заново. Генерация, сделанная по старому тексту, сбрасывается.

## Термины

- **Фраза** — запись `phrases`: кусок текста источника с target'ом. У слова может быть несколько фраз.
- **Карточка** — фраза, которую показывает review (`shown_by` задан).
- **Место** — ключ фразы (`OccurrenceKey`): где в документе стоит target.
- **Нарезка** — границы фразы внутри предложения; анализ выбирает их по `FragmentScore`.
- **Защищённая фраза** — с выбором (Learn / Cloze / Known / Skip), в Anki или с работой пользователя (правка, ручной выбор, добавлена вручную): `is_protected`. Ни одна операция её не меняет и не удаляет.
- **Решённое слово** — `is_decided`. Его фразы ни одна операция не меняет, показ не трогает. Проверяется первым.
- **Слово сделано на лету** — у леммы задан `LemmaKnowledge.elsewhere` (Known-список, Learn в другом источнике, Learning в Anki). Review уже показывает его карточку сделанной и ставит в Reviewed (`card_is_done`).
- **Слово выбыло** — анализ его больше не находит (повысился уровень, сменился порог частотности, поменялась логика отбора), и оно не сделано на лету.
- **Генерация** — Polish, Meaning, TTS фразы, media из видео (скриншот, клип).
- **Генерация по тексту** — Polish, TTS, media: сделаны из точного текста фразы.
- **Задача** — job генерации фразы в очереди или в работе.

## Update

Текст существующих фраз не меняется. Что делает, по порядку проверки для каждого слова:

1. **Решённое слово** — пропускается.
2. **Слово сделано на лету** — не удаляется, даже если анализ его не находит (анализ пропускает известные слова), и ни одна его фраза не удаляется и не меняется; пересчитываются только секции (п. 11).
3. **Выбывшее слово.** Незащищённые фразы удаляются вместе с генерацией и её файлами, задачи по ним отменяются. Слово удаляется, если его ничего не держит (`keeps_word`). Так при повышении уровня во всех источниках пропадают карточки слов ниже нового уровня, с их Polish и Meaning.
4. **Новое слово** (раньше в источнике не было, анализ теперь находит): фразы во всех местах, одна показана.
5. **Новое место** у существующего слова: добавляется фраза с нарезкой анализа.
6. **Тот же текст, другие данные.** Если анализ даёт для фразы тот же текст, но другие факты слов или позицию (`phrase_hash` другой), они переписываются без сброса генерации и без роста revision, как сейчас.
7. **Другой текст у того же места.** Фраза не меняется: это работа Re-cut.
8. **Место пропало, слово осталось.** Фраза без генерации и без задачи удаляется. Фраза с генерацией или задачей остаётся и участвует в выборе; на её строке (`block`, `line`) свежая фраза этого слова не вставляется, чтобы у места не было двух фраз.
9. **Ключи.** Фраза, ключ которой сдвинулся внутри строки при том же тексте, получает новый ключ (`_moved_keys`), как сейчас.
10. **Лучшее место.** Выбор заново ищет лучшую фразу слова (см. «Оценка фразы»), и показ может перейти на другую фразу. Генерация старой фразы остаётся при ней: если та снова станет лучшей, карточка вернётся со своей генерацией. Показ не уходит с фразы, у которой есть задача.
11. **Секции.** Заработанная секция пересчитывается у всех фраз без выбора и не в Anki, как сейчас.

## Re-cut phrases

Всё, что делает Update, кроме п. 7 и 8, вместо которых:

7. **Другой текст у того же места.** Незащищённая фраза нерешённого слова получает новый текст анализа, revision растёт.
   - Сбрасывается генерация по тексту: Polish (вместе с отменённым), TTS, media, с их файлами. Таймкоды media ставятся по новому тексту — после удаления старых записей, в той же транзакции.
   - Meaning остаётся.
   - Задачи в очереди переходят на новую revision и сработают по новому тексту. Задачи в работе отменяются.
8. **Место пропало, слово осталось.** Незащищённая фраза удаляется вместе с генерацией и файлами; показ переходит по п. 10.

## Оценка фразы

Выбор сравнивает фразы слова по оценке. Сейчас это `fragment_score`, посчитанный при нарезке, и при изменившемся знании он устаревает, а в Update текст не пересчитывается.

Оценка фразы для выбора — сохранённая `FragmentScore`, в которой поле `unknowns` заменено на `weight_unknown × unknowns_now`. Упакованное число разбирается и собирается только внутри `FragmentScore`: `FragmentScore.from_number(n)` (обратная `as_number`) и `with_unknowns(count)`; арифметики по разрядам вне value object нет.

- `unknowns_now` — число незнакомых слов исходной фразы (не Polish) кроме target'а по знанию `SectionRule.knowledge` — тому же, по которому считаются секции.
- Одна функция для всех кандидатов выбора: сохранённых фраз и свежих фраз анализа (`_fresh_row`).
- `weight_unknown` берётся из настроек отбора фраз (`ScoringConfig`): `SourceRebuilder` передаёт его в `plan_rebuild`.
- `fragment_score = None` остаётся `UNSCORED`.

Домен: `selection_score(stored: float | None, phrase: Phrase, knowledge: UserKnowledge, weight_unknown: int) -> float` — `FragmentScore.from_number(stored).with_unknowns(weight_unknown * unknowns_now).as_number()`.

## Кто какую операцию запускает

| Кто запускает | Операция |
|---|---|
| Пункт меню источника или набора источников | Update или Re-cut phrases |
| Смена уровня CEFR или настройки порога (`background_rebuild_launcher`) | Update |
| `make fix-sections` (`fix_sections`) | Update |
| Первая обработка источника (`process_source`) | Update (фраз ещё нет, результат тот же, что сейчас) |

У источников без своего текста (тема, Saved phrases) есть только Update; он пересчитывает секции (`plan_sections`). Re-cut им не предлагается.

## Модель

**Домен:**
- `SourceOperationKind`: `REBUILD` → `UPDATE`, добавляется `RECUT`. Обе — полноценные виды операции: блокировка, меню, подписи. `PREVIEW` остаётся одним видом, превью знает, чего оно (`previewed: UPDATE | RECUT`).
- `available_operations`: источник со своим текстом → `(UPDATE, RECUT)`; тема → `(REFRESH, UPDATE)`; Saved phrases → `(UPDATE,)`. `_MENU_ORDER = (REFRESH, UPDATE, RECUT)`.
- Подписи (`_BUSY_NAME`, `_BUSY_CAPTION`): `update` / `Updating…`, `re-cut` / `Re-cutting phrases…`, превью — `Checking what it changes…`.
- `RebuildMode(StrEnum)`: `UPDATE`, `RECUT` — `domain/value_objects`; вместо булева флага везде, где нужно знать, режет ли операция фразы.
- `plan_rebuild(..., mode: RebuildMode, done_on_the_fly: frozenset[WordKey])` вместо `include_open`. `done_on_the_fly` — слова источника, сделанные на лету, из того же снимка знаний, что и анализ.
- `_Planner._phrase`: правила Update п. 1–9 и Re-cut п. 7–8 вместо пары «touched / include_open». `is_touched` удаляется.
- `OccurrenceTextUpdate.reset_results` → `drop_text_generation`.
- `phrase_selection.is_frozen(o, include_open)` → `is_frozen(o)`: защищённая фраза или фраза с задачей. `select_phrases` ранжирует по `selection_score`.
- `OccurrenceRow` получает `has_polish` (`polished_phrase` задан, отменён или нет), `has_meaning`, `has_text_media` (TTS или media с файлом); `has_results` остаётся их «или» плюс cloze.

**Счётчики (`RebuildCounts`)**, каждый — по фразам плана:
- `words_added` — новые слова (п. 4);
- `words_removed` — удаляемые выбывшие слова (п. 3);
- `cards_lost_generation` — удаляемые показанные фразы с `has_polish`, `has_meaning` или `has_text_media` (п. 3, Re-cut п. 8);
- `cards_moved` — слова, показ которых перешёл на фразу без генерации (п. 10);
- `cards_recut` — фразы с новым текстом (Re-cut п. 7);
- `cards_recut_lost_text_generation` — из них с `has_polish` или `has_text_media`;
- `nothing_to_update` — план пуст.

`cards_new_phrase`, `cards_text_reset`, `cards_without_generation` удаляются.

**Application:**
- `RebuildRequest` удаляется.
- `SourceRebuilder.plan/apply(analysed, mode)`; `analyse` собирает `done_on_the_fly`.
- `RebuildSourceUseCase.execute/run/preview(source_id, mode)`; `ScopeOperationUseCase.rebuild/preview(scope, mode)`. Вид операции для блокировки — из `mode` одной таблицей `MODE_OPERATION: {UPDATE: SourceOperationKind.UPDATE, RECUT: SourceOperationKind.RECUT}`.
- `ScopeOperationUseCase.check/_targets` принимают отдельно вид блокировки и вид, который источник должен предлагать: у превью блокировка `PREVIEW`, а предлагаться должен `UPDATE` или `RECUT` по `of`. `_OFFERED` удаляется.
- `RebuildPreviewDTO`: `previewed` и одно поле `counts`; `RebuildSummaryDTO.include_open` → `kind`.

**Infrastructure:**
- `RebuildPlanWriter._rewrite`: при `drop_text_generation` обнуляет `polished_phrase`, `polish_reverted`, удаляет строки TTS и media; задачи в очереди переводит на новую revision (как `_queued_jobs_follow`), задачи в работе отменяет.
- Удаление фраз и сброс TTS / media удаляют и файлы на диске:
  - порт `MediaFiles` получает `remove(paths)`, реализация — `LocalMediaFiles`;
  - `apply_plan` возвращает пути файлов удаляемых строк TTS и media, прочитанные до удаления;
  - `SourceRebuilder.apply` вызывает `remove` после выхода из `unit_of_work.write()`.
- Задача TTS или media, которая уже работала и закончила после Rebuild, перед `keep()` проверяет `holds_revision` и при несовпадении выбрасывает черновик, чтобы не вернуть файл-сироту.

**API:**
- `POST /api/operations/update?scope=`, `POST /api/operations/recut?scope=` — без тела.
- `POST /api/operations/preview?scope=&of=update|recut`.

**Frontend:**
- `client.ts`: `update(scope)`, `recut(scope)`, `preview(scope, of)`; `types.ts`: `SourceOperationKind`, `SetOperation`, DTO.
- В меню источника и набора — пункты по `available_operations`: **Refresh**, **Update**, **Re-cut phrases**.
- `RebuildDialog` → `UpdateDialog` с `kind: 'update' | 'recut'`, без галочки. Тексты:

| Место | Update | Re-cut phrases |
|---|---|---|
| Заголовок | `Update “X”` | `Re-cut phrases of “X”` |
| До превью | `Finds new words, removes words you no longer need and moves cards to simpler sentences. Phrase texts and their Polish, Meaning and audio stay.` | `Also cuts every phrase again by the current logic. A phrase that changes loses its Polish, audio and video; Meaning stays.` |
| Превью и итог | `N new words, M words removed` | то же |
| | `K removed cards had Polish, Meaning or audio` (если > 0) | то же |
| | `N cards move to a simpler sentence — need ✨ there` (если > 0) | то же |
| | — | `N phrases get a new cut, K of them lose Polish or audio` (если > 0) |
| Пустой план | `Already up to date` + только Close | то же |

Сноска `The numbers may differ slightly from the result.` — только при непустом превью.

## Миграции

Нет. Схема не меняется, а строки `source_operations` стираются при каждом старте приложения (`release_source_operations`), так что строка `rebuild` от прошлой версии новому коду не попадётся.

## Риски

- После Re-cut Meaning объясняет target по старому тексту (`context=` в промпте). Если фраза стала короче, в объяснении может упоминаться то, чего во фразе уже нет.
- Update п. 8: фраза с генерацией, которую анализ больше не находит, остаётся кандидатом выбора со старыми структурными полями оценки.

## Тесты

- Update: новое слово → фразы во всех местах, одна показана; новое место → новая фраза; выбывшее слово с Polish, Meaning и TTS → удалено с файлами, задачи отменены, защищённая фраза того же слова осталась; слово сделано на лету и не найдено анализом → не удалено, все его фразы на месте, секции пересчитаны; решённое слово → не тронуто.
- Update: другая нарезка того же места → текст, Polish, Meaning, TTS, media не меняются; тот же текст с другими фактами → факты обновлены, revision прежняя.
- Update: место пропало → фраза без генерации удалена; с генерацией осталась, и на её строке не появилась вторая фраза слова, даже если ключ сместился при другом тексте.
- Update: выучил слова → показ переходит на фразу с меньшим `unknowns_now`; старая фраза сохранила генерацию; фраза с задачей показ не теряет.
- `selection_score`: разряд `unknowns` равен `weight_unknown × unknowns_now`, остальные разряды как в сохранённом `fragment_score`; `None` → `UNSCORED`.
- Re-cut: новая нарезка → текст новый, revision + 1, Polish (и отменённый), TTS, media удалены с файлами, Meaning на месте, таймкоды новые; задача в очереди на новой revision, задача в работе отменена.
- Re-cut: место пропало → фраза удалена с генерацией, показ перешёл.
- Тема и Saved phrases: только Update, меняет только секции; Re-cut не предлагается.
- Смена уровня и `fix_sections` запускают Update.
- Счётчики превью совпадают с итогом на том же состоянии; пустой план → `nothing_to_update`.
