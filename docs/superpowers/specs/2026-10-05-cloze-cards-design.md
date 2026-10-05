# Cloze-карточки: ручная разметка на ревью

## Задача

Сейчас любая карточка — на узнавание: фраза с выделенным target'ом → значение. Для слов, которые нужны в речи, полезнее карточка на вспоминание: фраза с пропуском, ответ надо вспомнить. Это особенно ценно для частицы фразового глагола и предлога, который управляется словом (`accused of`).

Пока всё ручное: пользователь сам решает, что карточка — cloze, и сам выбирает, какие слова скрыть. Автоматики (политики «кому делать cloze») нет.

Макеты: `docs/mockups/cloze-mockups.html`.

## Продуктовые решения

- Cloze **заменяет** карточку на узнавание: одна фраза — одна карточка.
- Решения на ревью: Learn `1` · Cloze `2` · Know `3` · Skip `4`.
- Скрываются только **целые слова**. Скрыть можно любые слова фразы, в том числе не входящие в target (предлог после слова).
- По умолчанию скрыт весь target.
- Подсказка: `none` · `translation` · `synonyms` · `first_letter` · `custom`. Дефолт — настройка `cloze_default_hint` (изначально `none`). `custom` в дефолте не бывает.
- В Anki ответ **не вводится** с клавиатуры (`{{type:}}` не используем).
- В Anki — отдельный нативный тип записи `AnythingToAnkiCloze`.
- Уже экспортированного кандидата в cloze превратить нельзя: записи в Anki не обновляются.

## Domain

### `CandidateCloze` (entity, frozen dataclass)

1:1 к кандидату, таблица `candidate_clozes` (Alembic).

| поле | тип | смысл |
|---|---|---|
| `candidate_id` | int | |
| `hidden_word_indices` | tuple[int, ...] | номера скрытых слов фразы, по возрастанию |
| `hint_kind` | `ClozeHintKind` | |
| `custom_hint` | str \| None | только для `custom` |
| `phrase` | str | снимок `card_phrase`, к которому относятся номера |

`ClozeHintKind` (StrEnum): `none`, `translation`, `synonyms`, `first_letter`, `custom`.

Cloze-карточка = `status == LEARN` и есть `CandidateCloze`. `CandidateStatus` не меняется, поэтому очередь экспорта, known words, статусы источника и правило готовности работают как раньше.

### `ClozeBuilder` (domain service)

- `words(phrase, lemma, surface_form)` → список `ClozeWord(index, text, is_target)`. Слова — части фразы между пробелами (как сейчас показывает `WordPicker`). `is_target` — слово без краевой пунктуации совпадает со словом target'а (`surface_form`, иначе `lemma`), без учёта регистра; разорванный фразовый глагол тоже распознаётся.
- `default_hidden(words)` → номера target-слов. Если ни одно не найдено — пустой набор, пользователь выбирает сам.
- `validate(words, indices)` — хотя бы одно слово, все номера в пределах фразы. Иначе `InvalidClozeError`.
- `cloze_text(phrase, indices)` → `She finally gave {{c1::up}} smoking last year.`
  - соседние скрытые слова объединяются в один `{{c1::…}}`;
  - разнесённые части получают тот же `c1` (одна карточка);
  - краевая пунктуация остаётся снаружи: `{{c1::year}}.`;
  - символы `}}` и `::` в слове экранируются так, чтобы не ломать синтаксис Anki.
- `front_preview(phrase, indices)` → та же фраза с `[…]` вместо пропусков (для превью в UI).
- `hint_text(kind, meaning, hidden_words, custom)`:
  - `translation` → `meaning.translation`, `synonyms` → `meaning.synonyms` (без markdown);
  - `first_letter` → первая буква каждого пропуска + `…`, через пробел;
  - `custom` → текст пользователя; `none` → пусто.
- `available_hints(meaning, hidden_words)` → виды, которые можно выбрать: `none`, `first_letter`, `custom` всегда; `translation`/`synonyms` — если есть текст и в нём нет ни одного скрытого слова (без учёта регистра, по границам слов).

### Смена фразы

Фраза меняется во многих местах (Edit text, Polish, revert Polish, Change boundary, Use as phrase), поэтому cloze сверяется с фразой лениво, при чтении: `ClozeBuilder.effective(cloze, candidate)`.
- `cloze.phrase == card_phrase` → разметка как есть;
- иначе → `hidden_word_indices = default_hidden` новой фразы, `phrase` — новая, подсказка сохраняется;
- target в новой фразе не найден → `None`: карточка ведёт себя как обычная (`LEARN` без cloze).

Через `effective` cloze читают DTO кандидата, превью и синк. Хранимая запись обновляется при следующем сохранении.

## Application

- `SaveClozeUseCase.execute(candidate_id, phrase, hidden_word_indices, hint_kind, custom_hint)`:
  - кандидат уже в Anki → `ClozeNotAllowedError` (API 409);
  - `phrase` (фраза, в которой выбраны индексы) ≠ `card_phrase` → `ClozePhraseChangedError` (API 409): фраза сменилась, пока открыт режим разметки, индексы указывают на другие слова;
  - валидирует через `ClozeBuilder`, `custom` требует непустой `custom_hint`, вид подсказки должен быть в `available_hints` → иначе `InvalidClozeError` (422);
  - сохраняет `CandidateCloze`, ставит `LEARN` через ту же логику, что `MarkCandidateUseCase` (known words, решения, статус источника).
- `PreviewClozeUseCase.execute(candidate_id, hidden_word_indices | None, hint_kind | None, custom_hint)` → `ClozePreviewDTO { phrase, words, hidden_word_indices, hint_kind, front, hint, available_hints, can_save }`. `phrase` — фраза, к которой относятся слова; `can_save` — то же правило, что у Save (≥1 скрытое слово, вид доступен, для `custom` — непустой текст). Без индексов — текущая разметка или дефолт; без вида — текущий или `cloze_default_hint` (если он недоступен — `none`).
- `MarkCandidateUseCase`: любая смена статуса удаляет cloze кандидата, кроме уже экспортированного — в Anki он лежит как cloze-заметка.
- DTO кандидата получает `cloze: { hidden_word_indices, hint_kind, custom_hint } | null` и `can_cloze: bool` (false, если кандидат уже в Anki).
- Настройка `cloze_default_hint` в `_SETTING_KEYS`, значения — виды без `custom`.

## Anki

- Тип `AnythingToAnkiCloze` (`isCloze: true`), поля: `Text`, `Hint`, `Target`, `IPA`, `Meaning`, `Translation`, `Synonyms`, `Examples`, `Image`, `Audio`, `AudioTargetUS`, `AudioTargetUK`, `AudioTTS`. Имена фиксированные, маппинга в настройках нет.
- Шаблоны: `anki-templates/cloze-front.html`, `anki-templates/cloze-back.html`, CSS общий `style.css` (+ стили `.cloze` и `.hint`). Front: картинка, `{{cloze:Text}}`, `Hint` — без аудио: озвучка фразы произносит скрытые слова. Аудио — только на Back. Back: `{{cloze:Text}}`, далее как у обычной карточки.
- `AnkiConnector.ensure_note_type(..., is_cloze: bool = False)` — при создании модели передаёт `isCloze`.
- `AnkiConnector.find_notes_by_target(deck, model, target_field, target)` — поиск дублей по нужной модели и полю. Чинит захардкоженный `AnythingToAnkiType`.
- `SyncToAnkiUseCase`: сборка записи вынесена в два сборщика — `RecognitionNoteBuilder` (как сейчас) и `ClozeNoteBuilder`. Для каждого кандидата выбирается сборщик по наличию cloze; обе модели гарантируются (`ensure_note_type`) только если в партии есть их карточки. Медиа и дедупликация общие.

## API

- `PUT /api/candidates/{id}/cloze` — тело `{phrase, hidden_word_indices, hint_kind, custom_hint}` → кандидат. 404 / 409 / 422.
- `POST /api/candidates/{id}/cloze/preview` — тело `{hidden_word_indices?, hint_kind?, custom_hint?}` → `ClozePreviewDTO`.

## Frontend

- `DecisionButtons`: Learn `1`, Cloze `2`, Know `3`, Skip `4`; клавиатура ревью переназначается так же. Cloze неактивна, если `can_cloze == false`.
- Нажатие Cloze (или `2`) включает режим разметки текущей карточки (локальный UI-state):
  - `CardPhrase` показывает слова из превью как кнопки; клик переключает скрытие; target подчёркнут; скрытое не-target слово помечено точкой;
  - `ClozePanel` под фразой: переключатель подсказки (недоступные виды выключены), поле для `custom`, превью «Anki front», Cancel `Esc`, Save cloze `↵`;
  - каждый клик/смена подсказки → `preview`; Save → `PUT` с `phrase` из превью; сменилась фраза карточки — превью запрашивается заново с дефолтной разметкой;
  - Learn/Know/Skip в режиме разметки сначала закрывают его;
- Cloze-карточка вне режима разметки: скрытые слова в пунктирной рамке, в фактах метка `cloze · hint: …`; клик по фразе или `2` — снова режим разметки.
- Список фраз и экран экспорта: бейдж `cloze`.
- Settings → Review: строка «Default cloze hint» (segmented: No hint / Translation / Synonyms / First letter).

## Тесты

- Unit `ClozeBuilder`: пунктуация, регистр, разорванный фразовый глагол, соседние и разнесённые пропуски, экранирование, утечка подсказки, first letter.
- Unit use cases: сохранение, 409 для экспортированного, 422 для невалидного, удаление cloze при смене статуса, пересборка при смене фразы.
- Unit sync: cloze-запись, `ensure_note_type` с `is_cloze`, дедупликация по модели.
- Integration API: `PUT`/`preview`.
- Frontend (vitest): раскладка клавиш решений.
