# Источник «From everywhere» — фразы, собранные отовсюду

## Зачем

Фразы встречаются где угодно: пост, переписка, вывеска, реплика в подкасте. У них нет «источника», который имело бы смысл добавлять целиком. Нужен способ быстро сохранить одну фразу с выбранным target'ом, не создавая под неё отдельный источник.

## Продуктовое поведение

- В приложении всегда есть один встроенный источник **From everywhere**. Своего текста у него нет — только набор фраз, добавленных вручную. Каждая фраза — отдельный кандидат (будущая карточка).
- В форме добавления источника после вкладки **Topic** — вкладка **Phrase**:
  1. вставляю фразу;
  2. фраза разбивается на слова-чипы, тапаю слова target'а (слово, фразовый глагол, коллокация);
  3. **Add phrase** — фраза с target'ом сохраняется в From everywhere.
- Добавленная фраза сразу считается решённой «учить» (`learn`): я выбрал её сам, повторное ревью не нужно. Дальше — обычный путь: генерация значений, экспорт, синк в Anki — из экрана источника.
- Одну и ту же фразу можно добавить несколько раз с разными target'ами.
- From everywhere нельзя удалить и переобработать (обрабатывать нечего). Переименовать и положить в коллекцию — можно.
- Фразу не полируем через AI: пользователь выбрал её такой, какой она встретилась.
- Экран ревью показывает только список фраз — исходного текста нет (как у Topic).

## Техническое решение

**Domain**
- `ContentType.PHRASES = "phrases"`, `InputMethod.PHRASE_ADDED = "phrase_added"`.
- `Source.everywhere()` — фабрика встроенного источника (`title="From everywhere"`, пустой `raw_text`, статус `done`).
- `Source.is_permanent` (нельзя удалить и переобработать), `Source.has_text` (есть ли что показать в ревью), `can_polish_phrases = False` и `searchable_text = None` для PHRASES.
- `SourceRepository.get_by_content_type(...)`.
- Исключения `PermanentSourceError`, `TargetNotInPhraseError`.

**Application**
- `AddEverywherePhraseUseCase.execute(phrase, target)`: валидирует (фраза и target непустые, target входит во фразу), находит или создаёт источник From everywhere, строит кандидата через `CandidateFactory` со статусом `learn`, пересчитывает статус ревью источника.
- `CreateSourceUseCase` отклоняет `phrase_added` — второй такой источник создать нельзя.
- `DeleteSourceUseCase` и `ReprocessSourceUseCase` отклоняют permanent-источник.
- `SourceDTO.is_permanent`, `SourceDetailDTO.has_source_text` — фронт не решает это сам по `content_type`.

**Infrastructure**
- Alembic-миграция создаёт строку From everywhere, чтобы источник был в списке сразу (use case всё равно создаёт его, если строки нет).
- `POST /sources/everywhere/phrases {phrase, target}` → `StoredCandidateDTO`; 400 на ошибку валидации. Delete/reprocess permanent-источника → 409/400.

**Frontend**
- Вкладка `Phrase` в `AddSourceForm`, выбор target'а — общий компонент `WordPicker` (тот же, что в попапе выделения на экране ревью).
- Иконка источника — `Globe`, подпись `Phrases`. Меню строки скрывает Delete/Reprocess по `is_permanent`.
