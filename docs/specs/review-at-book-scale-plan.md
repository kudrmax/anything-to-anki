# Review at Book Scale — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** нажатие в ревью коллекции размером с книгу стоит десятки миллисекунд, а состояние карточек всегда верно.

**Architecture:** вычисляемое состояние карточек хранится в проекции. Её обновляет проектор по явным событиям владельцев фактов перед каждым коммитом единственного Unit of Work. Фронт получает окно карточек и текст кусками при прокрутке.

**Tech Stack:** Python 3.12, SQLAlchemy 2, SQLite, Alembic, FastAPI, hypothesis (новая dev-зависимость), React + TypeScript.

**Spec:** `docs/specs/review-at-book-scale.md` (коммит `9357da32`).

## Как устроен этот план

План общий: в нём все этапы, их результат, интерфейсы и проверка. Пошагово (TDD) расписан только этап 1. Пошаговый план каждого следующего этапа пишется в его начале, в этот же файл: интерфейсы этапов 3–7 зависят от кода, который появится в этапах 1–2.

Каждый этап — своя ветка от `perf/collection-review` и своё вливание. Перед каждым вливанием:
- `make lint`, `make typecheck`, `make test`;
- для фронта — `npm run lint` и `npm run build`.

Всё должно быть зелёным.

## Global Constraints

- Правила только в domain. SQL выбирает и сортирует готовые значения, фронт ничего не вычисляет.
- `mypy --strict`, без `Any` без комментария; `dataclass(frozen)` в domain, pydantic в DTO.
- Схема — только Alembic. `downgrade` у миграций с потерей данных — `NotImplementedError`.
- Процессы — только через make. Проверка — в worktree на копии базы, prod не трогать.
- Коммиты: conventional commits, без упоминания Claude.
- Порог частотности ∈ `THRESHOLD_STEPS` = (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, None).

## Review Focus

1. **Удаление источника, в котором было Learn**: в других источниках карточки этой леммы снова открыты, а фразы с ней пересчитаны. Тест — в этапе 5, сценарий дифференциального теста.
2. **Rebuild большой главы, пока открыто ревью**: ревью не падает с `database is locked`, нажатие ждёт не дольше одной транзакции источника. Тест — в этапе 8, замер.
3. **Жалоба с «не знаю» на слово, которое учишь**: ничего не меняется. Тест — в этапе 3, строка таблицы U*.
4. **Переход к карточке в далёкой главе по клику в тексте**: открывается окно вокруг неё, без загрузки всего, что перед ней. Тест — в этапе 6.
5. **Перезапуск сервера при открытом ревью**: ревью переоткрывается на текущей карточке, без ошибки. Тест — в этапе 6.

---

## Этап 0. Стенд на Worm и исходные цифры

Результат: воспроизводимые копии базы и скрипт замера. Им пользуются этапы 5 и 8.

**Files:**
- Create: `scripts/bench/build_worm_db.py`. Из `DATA_DIR` и пути к epub строит копию базы с коллекцией: делит книгу на главы и обрабатывает первые N глав. Копия делается через backup API SQLite.
- Create: `scripts/bench/bench_review.py`. На копии базы меряет use case'ы ревью: открытие, нажатия Known/Learn/Skip по выборке лемм (медиана, p95, p99, максимум), счётчики, пересборку. Печатает таблицу и пишет JSON в `--out`.
- Modify: `Makefile` — цели `bench-db` (`EPUB=… CHAPTERS=… OUT=…`) и `bench-review` (`DB=… OUT=…`). Обе работают с копией, а не с `data/`.

- [ ] Собрать копии: 25 глав, 100 глав, вся книга.
- [ ] Снять исходные цифры на нынешнем коде; сохранить JSON в `docs/specs/review-at-book-scale-bench/baseline.json`.
- [ ] Коммит: `chore: worm bench database and review benchmark`.

## Этап 1. Единственный путь коммита (пошагово — ниже)

Результат: транзакцию открывает и коммитит только `SqlaUnitOfWork.write()`. Session не выходит за пределы `infrastructure/persistence` и DI. Поведение не меняется.

## Этап 2. Владельцы фактов и события

Результат: порт `ChangeRecorder` в domain; владельцы создают события. Проектора пока нет: записанные события только копятся и очищаются при коммите.

**Interfaces (produces):**
- `domain/value_objects/card_change.py`: frozen-dataclass'ы `DecisionChanged(lemma: str)`, `PhraseChanged(phrase_id: int)`, `WordsChanged(source_id: int, lemmas: frozenset[str])`, `SourceDeleted(source_id: int, lemmas: frozenset[str])`, `MarkChanged(lemma: str)`, `BindingChanged(lemma: str)`, `CardContentChanged(phrase_id: int)`, `WordContentChanged(word_id: int)`, `LevelChanged()`. Union `CardChange`. Лемма — в нижнем регистре, нормализуется в `__post_init__`.
- `domain/ports/change_recorder.py`: `class ChangeRecorder(ABC): record(change: CardChange) -> None; drain() -> list[CardChange]`.
- Владельцы (спека, раздел 3) получают `ChangeRecorder` в конструктор через `container.py`.

**Проверка:** `tests/unit/architecture/test_owner_events.py`. Каждый пишущий метод портов-владельцев перечислен в `WRITE_CASES` (фикстура и ожидаемое событие) или в `READ_ONLY`. Метод, которого нет ни там, ни там, роняет тест; метод из `WRITE_CASES` без события — тоже.

### Этап 2 пошагово

Ветка `perf/change-events` от `perf/collection-review`.

- **Task 2.1 — события и их хранение.** `card_change.py` (события из «Interfaces» выше, леммы в нижнем регистре); порт `ChangeRecorder` (`record`, `drain`); `SessionChangeRecorder` в `infrastructure/persistence/` хранит события в `session.info`, общие для всех владельцев на сессии; `SqlaUnitOfWork.write()` перед коммитом отдаёт события в `before_commit` (пока пусто) и очищает их, при откате — очищает. Тесты: нормализация, общий список на сессию, события дошли до `before_commit` один раз при коммите и не дошли при откате.
- **Task 2.2 — владельцы пишут события.** Таблица «порт → пишущие методы → событие» (решение по слову, фразы, Rebuild, слова, удаление источника с леммами до удаления, отметки, привязки, уровень, генерация). Тест `test_owner_events.py`: каждый публичный метод порта-владельца — в `READ_ONLY` или в `WRITE_CASES` (вызов на настоящей реализации и ожидаемые события); метод вне обоих списков роняет тест.

## Этап 3. Domain: правило статусов и разделы при каждом пороге

Результат: правила, на которых строится проекция. Поведение меняется только по правилу статусов (спека, раздел 1).

**Interfaces (produces):**
- `THRESHOLD_STEPS`, `step_index(zipf: float | None) -> int`. Калибратор и `FREQUENT_WORD_THRESHOLDS` выражены через них; порог вне набора — `ValueError`.
- `newness(word: Word, vocabulary: Vocabulary, user_level: CEFRLevel) -> Newness`, где `Newness ∈ {ALWAYS, IF_RARE, NEVER}`. `UserKnowledge.is_new` выражен через неё.
- `PhraseNewness.of(words) -> PhraseNewness` с `count(step) -> int`.
- `sections_by_step(card) -> tuple[CandidateSection, ...]` (длина 8).
- Таблица U* и эффект `FORGET_UNKNOWN` в `decision_rules.py`; маска Unknown в `card_choice.py:210`, `lemma_knowledge.py` и `vocabulary.py` удалена.

**Проверка:**
- `section_of` для каждого шага совпадает с `sections_by_step` на всех фикстурах карточек;
- тест покрытия ключей таблиц (уже есть) расширен на U*;
- тест «жалоба с “не знаю” на лемме с Learn ничего не меняет».

### Этап 3 пошагово

Ветка `perf/domain-steps` от `perf/collection-review`.

- **Task 3.1 — пороги, новизна слова, разделы при каждом шаге.** `THRESHOLD_STEPS` и `step_index`; калибратор и ручные ключи через них; `Newness` и `newness()`, через которую выражен `is_new`; `PhraseNewness`; `sections_by_step`. Поведение не меняется: существующие тесты без правок, равенство `sections_by_step` и `card_section` на всех шагах для фикстур; разовая сверка на копии Worm (100 глав) — 0 расхождений.
- **Task 3.2 — пять взаимоисключающих статусов.** Эффект `FORGET_UNKNOWN` в таблицах нажатий для Learn/Cloze на лемме из Unknown; правило отметки «не знаю» (`unknown_mark`: отметить / отметить и снять Known / ничего для «учу» и «в Anki»); жалоба и Settings следуют ему; мёртвая маска Unknown удаляется, защитный приоритет остаётся до миграции этапа 4. Тесты по каждой строке правила из спеки, раздел 1.

## Этап 4. Таблицы и миграция

Результат: `word_marks` и `known_pos` вместо `known_words` и `unknown_words`; `candidates.status` удалён; `card_choice` пишется только при исчезновении карточки; правила читают факты, а не `candidates.status`.

**Files:** миграция `00NN_word_marks_and_status.py` (номер — проверить все ветки перед выбором); модели; `sqla_known_word_repository.py`, `sqla_unknown_word_repository.py` → `sqla_word_mark_repository.py`; `sqla_learning_query.py`; `sqla_word_state_repository.py`; `sqla_anki_sync_repository.py`; 13 читателей `candidates.status`.

**Проверка:**
- миграционный тест на синтетической базе со всеми видами конфликтов из спеки (раздел 8): ожидаемые итоги и строки лога в `data/migration-NN.log`;
- прогон миграции на копии dev-базы и копии Worm: число конфликтов в логе, после миграции `make test` зелёный.

### Этап 4 пошагово

Ветка `perf/word-marks` от `perf/collection-review`. Номера миграций: 0053 занят в другой ветке, этот этап берёт 0054 и 0055.

Решение при исполнении: удаление `candidates.status` переносится в этап 5 — без проекции его читателям пришлось бы считать статус в SQL, то есть повторить правило `decision_status` (принцип 4 спеки).

- **Task 4.1 — одна таблица отметок.** Миграция 0054: `word_marks(lemma PK, mark, created_at)` и `known_pos(lemma, pos)`; слияние по `lower(lemma)`, конфликт known/unknown — по более позднему `created_at`, пустой pos поглощает остальные, лог `data/migration-0054.log`. `WordMarkRepository` вместо двух репозиториев, `MarkChanged` на каждую запись. Settings ведут себя как раньше. Защитный приоритет Unknown над Known из этапа 3 удаляется.
- **Task 4.2 — выбор привязки как факт; старые конфликты.** `card_choice` пишется один раз — перед удалением карточки или источника, вызовом владельца Anki; `bind()` и сохранение слова его больше не пишут. Миграция 0055: `card_choice` nullable, NULL у живых привязок; два решения по одной лемме — привязка, потом более поздний `studied_at`, потом меньший id; Unknown рядом с «учу» или действующей привязкой снимается. Лог `data/migration-0055.log`. Плюс доводки после ревью 3.2.

## Этап 5. Проекция

Результат: `lemma_states`, `card_states`, `phrase_words`; `CardStateProjector` применяет события перед каждым коммитом `write()`; задача времени в воркере; пересборка при запуске; WAL; `make card-states-check`. Ревью и экран источников читают проекцию.

**Interfaces (produces):**
- `application/utils/card_state_projector.py`: `CardStateProjector.apply(changes: list[CardChange]) -> None`, `rebuild() -> None`.
- Порт `domain/ports/card_state_store.py`: `CardStateStore` (запись строк, счётчики по scope, строки окна, изменения после ревизии).
- `LiveCardStates` — полный расчёт нынешним кодом, эталон для тестов и `card-states-check`.

**Проверка:**
- `tests/integration/test_card_state_projection.py`: дифференциальный тест на `hypothesis` (stateful, фиксированный seed, `deadline=None`, < 10 с). Генератор строится по `WRITE_CASES` из этапа 2. После каждого шага проекция совпадает с `LiveCardStates`: статусы, разделы, счётчики, порядок каждой сортировки из enum.
- Сценарии Review Focus 1.
- Повтор замера прототипа на копии Worm через `make bench-review`: цифры не хуже прототипа (спека, раздел 9).

## Этап 6. API и фронт ревью: окно и ленивый список

Результат: `review_id`; мутации отвечают изменениями и следующей карточкой; строки списка с разделами готовит сервер; ленивая подгрузка списка в обе стороны; «Show more» и `useShownCandidates` удалены.

**Проверка:**
- тесты use case'ов окна, фокуса и правил новых карточек (спека, раздел 7);
- тесты фронта: обёртка `mutate → refresh` единственная, фронт не считает разделы и фокус;
- Review Focus 4 и 5.

## Этап 7. Текст справа кусками

Результат: оглавление документов и куски по абзацам с абсолютным номером блока; подгрузка в обе стороны; правка границы открывает текст на позиции фразы.

**Проверка:**
- тест: граница куска не делит блок;
- выделение внутри блока работает, выделение через два блока отклоняется, как сейчас.

## Этап 8. Тесты на всём Worm и замер скорости

Результат: решение «готово или нет» с цифрами. Проверка в worktree на копии всей книги (121 тыс. карточек), в браузере на видимой вкладке.

- [ ] Собрать свежую копию всей книги (`make bench-db`), запустить worktree на ней.
- [ ] **Правильность:** скрипт проходит 300 смешанных действий:
  - Learn, Known, Skip и отмены;
  - «не знаю» из жалобы;
  - правки границы и polish;
  - замена примером;
  - Update и Re-cut главы;
  - удаление главы;
  - сдвиг часов через 30 дней.

  После каждого 25-го действия `make card-states-check` показывает 0 расхождений.
- [ ] **Скорость сервера** (`make bench-review`, 200 нажатий по случайным леммам).
- [ ] **Скорость в браузере:** 30 нажатий подряд, от клавиши до отрисовки следующей карточки; открытие ревью; подгрузка куска при прокрутке.
- [ ] **Тяжёлые операции:** Rebuild главы при открытом ревью; смена уровня; запуск приложения.
- [ ] Записать цифры в `docs/specs/review-at-book-scale-bench/final.json` и таблицу «было / стало» в этот план.

**Пороги «ок»:**

| Что | Порог |
|---|---|
| Нажатие в браузере, от клавиши до новой карточки | p95 ≤ 150 мс, максимум ≤ 400 мс |
| Нажатие на сервере (решение + проекция) | p99 ≤ 60 мс; самая частая лемма книги ≤ 200 мс |
| Открытие ревью до первой карточки | ≤ 1,5 с |
| Подгрузка куска списка или текста | ≤ 150 мс |
| Нажатие во время Rebuild главы | ≤ 2 с, без ошибки |
| Запуск приложения (миграции + пересборка) | ≤ 10 с |
| Смена уровня | ≤ 10 с |
| `card-states-check` после сценария | 0 расхождений |

- [ ] **Если хоть один порог не выполнен** — остановиться и сказать Максу прямо: какой порог, какие цифры, где уходит время (профиль), какие есть варианты. Решаем вместе. Подгонять пороги или замер под результат нельзя.

---

## Этап 1 пошагово

Ветка: `perf/single-commit-path` от `perf/collection-review`.

### Task 1.1: Тест пути коммита

**Files:**
- Create: `backend/tests/unit/architecture/test_commit_path.py`

- [ ] **Step 1: Написать тест.**
  - Сканируются все `.py` в `backend/src/backend`. Строки с `.commit(`, `.begin(`, `begin_nested(`, `sessionmaker(` и `Session(` допустимы только в `infrastructure/persistence/` и `infrastructure/api/dependencies.py`.
  - Тест `test_no_commit_outside_persistence`: `assert offenders == []`, где `offenders` — список `путь:строка: текст`.
  - Тест `test_sessions_only_in_persistence_and_di`: тип `Session` импортируется только там же, а также в `infrastructure/container.py`.
- [ ] **Step 2: Запустить**: `make test` (или `pytest backend/tests/unit/architecture/test_commit_path.py`). Ожидается FAIL со списком из ~34 файлов. Список сохранить: это чек-лист задач 1.3–1.6.

### Task 1.2: Unit of Work — единственная дверь

**Files:**
- Modify: `backend/src/backend/domain/ports/unit_of_work.py`, `backend/src/backend/infrastructure/persistence/sqla_unit_of_work.py`
- Test: `backend/tests/integration/test_sqla_unit_of_work.py` (создать)

**Interfaces (produces):** `UnitOfWork.write() -> AbstractContextManager[None]` остаётся единственным способом записи. `commit()` и `rollback()` уходят из порта. Повторный вход в `write()` — `NestedWriteError` (domain exception).

- [ ] **Step 1: Тесты:**
  - `test_write_commits_on_exit`;
  - `test_write_rolls_back_on_error`;
  - `test_nested_write_raises` — `with uow.write(): with uow.write(): ...` → `NestedWriteError`;
  - `test_write_does_not_commit_outside_work` — объекты, добавленные в сессию до `write()`, не попадают в базу при входе в `write()`. Сейчас `write()` коммитит их на входе, `sqla_unit_of_work.py:36`; вместо этого — откат несохранённого и предупреждение в лог.
- [ ] **Step 2:** запустить, ожидается FAIL на трёх последних.
- [ ] **Step 3:** реализовать; удалить `commit()`/`rollback()` из порта и всех реализаций, включая фейки в `backend/tests`.
- [ ] **Step 4:** тесты зелёные.
- [ ] **Step 5:** коммит `refactor: unit of work is the only way to write`.

### Task 1.3: Use case'ы пишут через `write()`

**Files:** use case'ы из списка Task 1.1 в `application/`: `manage_settings.py`, `process_source.py`, `rebuild_source.py`, `refresh_topic.py`, `scope_operation.py`, `utils/source_rebuilder.py` — и все use case'ы, которые сейчас полагаются на коммит в роуте.

- [ ] Для каждого use case'а, который пишет: тело записи обернуть в `with self._uow.write():`. Промежуточные коммиты (`rebuild_source.py:61,66,87`, `process_source.py:81,104`) становятся отдельными `write()`.
- [ ] Существующие тесты use case'ов зелёные. Где тест проверял коммит роута, проверяется видимость записи из новой сессии.
- [ ] Коммит `refactor: use cases write through the unit of work`.

### Task 1.4: Роуты не управляют транзакциями

**Files:** `infrastructure/api/routes/*.py` (19 файлов из списка), `infrastructure/api/background.py`, `infrastructure/api/dependencies.py`.

- [ ] Роуты получают use case'ы из контейнера, а не `Session`. `session.commit()` удалить. `get_db_session` остаётся только внутри `dependencies.py` для сборки use case'ов.
- [ ] `infrastructure/api/background.py`: фоновые задачи строят use case'ы через контейнер, без своей сессии.
- [ ] Тесты роутов зелёные.
- [ ] Коммит `refactor: routes no longer commit`.

### Task 1.5: Воркер без `session_scope`

**Files:** `infrastructure/container.py:389-401, 915`, `infrastructure/queue/job_worker.py`, `claimed_run.py`, `tts_subprocess.py`, `infrastructure/services/lazy_media_reconciler.py`, `persistence/sqla_parse_cache.py`, `cli/build_dict_cache.py`.

- [ ] Удалить `Container.session_scope`. Задания воркера строят use case'ы на сессии из общей фабрики и пишут через `write()`.
- [ ] Удалить отдельный `sessionmaker` для фоновой пересборки (`container.py:915`); фоновая пересборка использует общую фабрику.
- [ ] Тесты воркера зелёные.
- [ ] Коммит `refactor: worker writes through the unit of work`.

### Task 1.6: Закрыть этап

- [ ] `test_commit_path.py` зелёный.
- [ ] `make lint`, `make typecheck`, `make test` зелёные.
- [ ] Worktree на копии dev-базы: открыть ревью, нажать Learn, Known и Skip, добавить слово, обработать источник. Всё работает как до этапа.
- [ ] Влить `perf/single-commit-path` в `perf/collection-review` (`--no-ff`).
