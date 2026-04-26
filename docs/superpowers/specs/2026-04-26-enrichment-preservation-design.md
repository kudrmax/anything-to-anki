# Enrichment Preservation при Reprocessing

## Проблема

При reprocessing источника все candidates удаляются деструктивно. Вместе с ними теряются дорогие enrichment-данные: meaning (AI-генерация), pronunciation (скачанные аудио), TTS (синтез речи), media (скриншоты и аудио-клипы из видео). Даже если после reprocessing появляется candidate с тем же target и фразой — enrichment генерируется заново.

## Решение

Перед удалением candidates сохранять enrichment в таблицу `enrichment_cache`. После завершения pipeline — восстанавливать enrichment для candidates, у которых `(lemma, pos, context_fragment)` совпали побайтово.

Удаление остаётся полностью деструктивным. Enrichment cache — best-effort: если restore упал, данные просто теряются как раньше, но candidates сохраняются.

## Что сохраняем

| Enrichment      | Сохраняем | Почему                                      |
|-----------------|-----------|-----------------------------------------------|
| Meaning         | Да        | AI-генерация, дорого                          |
| Pronunciation   | Да        | Скачивается из словарей                       |
| TTS             | Да        | Синтез речи                                   |
| Media           | Да        | Скриншоты + аудио-клипы из видео              |
| CEFR breakdown  | Нет       | Пересчитывается — reprocessing для этого и нужен |
| Статус (LEARN/KNOWN/SKIP) | Нет | Пересчитывается                        |
| Anki sync mapping | Нет     | Пересчитывается                               |

## Критерий совпадения

Строгое побайтовое совпадение `(lemma, pos, context_fragment)`. Все три поля. Если хоть что-то отличается — enrichment не восстанавливается.

## Архитектура: порт `EnrichmentCacheRepository`

Use cases не знают о SQL и таблицах. Взаимодействие с `enrichment_cache` — через порт (ABC в `domain/ports/`).

```python
class EnrichmentCacheRepository(ABC):
    @abstractmethod
    def save_from_source(self, source_id: int) -> None:
        """Скопировать enrichment всех candidates источника в cache.

        Matching criteria: (lemma, pos, context_fragment) — побайтовое совпадение.
        При дубликатах (lemma, pos, context_fragment) — ON CONFLICT REPLACE.
        """

    @abstractmethod
    def restore_to_candidates(self, source_id: int) -> int:
        """Восстановить enrichment для совпавших candidates. Вернуть кол-во восстановленных.

        Matching criteria: (lemma, pos, context_fragment) — побайтовое совпадение.
        Восстанавливает: meaning, media, pronunciation, TTS.

        Media: pipeline уже мог вставить media-запись с таймкодами (start_ms, end_ms).
        Restore заменяет всю media-запись целиком (screenshot, audio, таймкоды) данными из кэша.
        """

    @abstractmethod
    def cleanup(self, source_id: int) -> None:
        """Удалить cache для source_id."""

    @abstractmethod
    def cleanup_all(self) -> None:
        """Удалить всё из cache (для reconcile при старте)."""
```

SQL-реализация (`INSERT INTO ... SELECT`, JOIN'ы) — в `infrastructure/persistence/sqla_enrichment_cache_repository.py`. Данные не покидают infrastructure — entity/VO для кэша не нужен, порт оперирует только `source_id`.

## Таблица `enrichment_cache`

Постоянная таблица (не TEMP), создаётся через Alembic-миграцию.

```
enrichment_cache:
  source_id                  INTEGER NOT NULL
  lemma                      VARCHAR(100) NOT NULL
  pos                        VARCHAR(10) NOT NULL
  context_fragment           TEXT NOT NULL
  -- meaning
  meaning                    TEXT
  translation                TEXT
  synonyms                   TEXT
  examples                   TEXT
  ipa                        VARCHAR(100)
  meaning_generated_at       DATETIME
  -- media
  screenshot_path            TEXT
  audio_path                 TEXT
  start_ms                   INTEGER
  end_ms                     INTEGER
  media_generated_at         DATETIME
  -- pronunciation
  us_audio_path              TEXT
  uk_audio_path              TEXT
  pronunciation_generated_at DATETIME
  -- tts
  tts_audio_path             TEXT
  tts_generated_at           DATETIME

  PRIMARY KEY (source_id, lemma, pos, context_fragment)
```

## Flow и транзакции

### Текущий reprocess flow

```python
# Route: reprocess endpoint
reprocess_use_case.execute(source_id)   # delete candidates + reset source
session.commit()

# Route: _process_background (новая сессия)
process_source.execute(source_id)       # создаёт новые candidates
bg_session.commit()
```

### Новый flow

`ReprocessSourceUseCase` — полный оркестратор reprocessing, включая enrichment preservation. Вся логика — в use case, route остаётся тонкой обёрткой.

```python
# ReprocessSourceUseCase.execute(source_id):
#   1. enrichment_cache_repo.save_from_source(source_id)
#   2. candidate_repo.delete_by_source(source_id)
#   3. source.reset_to_initial_state()

# ReprocessSourceUseCase.finalize(source_id):
#   1. enrichment_cache_repo.restore_to_candidates(source_id)
#   2. enrichment_cache_repo.cleanup(source_id)
#   Обёрнуто в savepoint + try/except.
```

```python
# Route: reprocess endpoint
reprocess_use_case.execute(source_id)   # save cache + delete + reset
session.commit()                        # Транзакция 1

# Route: _process_background (новая сессия bg_session)
process_source.execute(source_id)       # создаёт новые candidates
reprocess_finalize_uc.finalize(source_id)  # restore + cleanup (best-effort)
bg_session.commit()                     # Транзакция 2
```

**Важно:** `finalize()` вызывается на экземпляре use case, созданном с `bg_session` (не с первой сессией). В `_process_background` создаётся свой `container.reprocess_source_use_case(bg_session)` — иначе restore не увидит новые candidates, которые ещё не закоммичены.

### Транзакционные гарантии

- **Транзакция 1:** `save_from_source` + `delete_by_source` + `reset_to_initial_state` атомарны. Если упали — ни cache не записан, ни candidates не удалены. Чисто.
- **Транзакция 2:** `process_source.execute` создаёт candidates. Затем `finalize` пытается восстановить enrichment внутри savepoint. Если restore упал — savepoint откатывается, candidates остаются, enrichment потерян (как раньше). Если всё ок — candidates + enrichment фиксируются вместе.

### Error handling в finalize

`finalize` оборачивает restore и cleanup в `session.begin_nested()` (savepoint) + try/except. При ошибке — откатываем savepoint (убираем частично вставленные enrichment-записи) и логируем warning. Candidates не страдают.

```python
def finalize(self, source_id: int) -> None:
    try:
        with self._session.begin_nested():  # savepoint
            restored = self._enrichment_cache_repo.restore_to_candidates(source_id)
            self._enrichment_cache_repo.cleanup(source_id)
        logger.info("enrichment restore: %d candidates restored (source_id=%d)", restored, source_id)
    except Exception:
        logger.warning("enrichment restore failed (source_id=%d), continuing without", source_id, exc_info=True)
```

## Конфликт media с pipeline

Pipeline (`process_source.execute`) вставляет media-записи с таймкодами (`start_ms`, `end_ms`) для video-источников. При restore из кэша для того же candidate возникает конфликт PK в `candidate_media`.

Решение: `restore_to_candidates` использует `INSERT OR REPLACE` для media. Кэш содержит полную media-запись (screenshot, audio, таймкоды) — она заменяет media-запись pipeline целиком. Если фраза совпала побайтово — таймкоды те же, screenshot и audio из кэша восстановлены.

## Дубликаты при save

В одном source может быть несколько candidates с одинаковым `(lemma, pos, context_fragment)` — например, рефрен в lyrics. `save_from_source` использует `INSERT OR REPLACE` — последний enrichment перезапишет предыдущий. Это допустимо: enrichment для идентичных (lemma, pos, context_fragment) будет одинаковым.

## Параллельный reprocess

Несколько source'ов могут reprocess одновременно. Каждый работает со своим `source_id` в `enrichment_cache` — конфликтов нет. Колонка `source_id` в составном PK это гарантирует.

Покрыть тестом: два source reprocess параллельно, enrichment восстанавливается корректно для каждого.

## source_id стабилен

Source не удаляется при reprocessing — обновляется на месте (`reset_to_initial_state()` сохраняет `id`). Старые и новые candidates ссылаются на тот же `source_id`. Lookup в `enrichment_cache` по `source_id` корректен.

Проверено в коде: `reprocess_source.py:53` — `delete_by_source(source_id)` удаляет candidates, не source. `source.py:38` — `reset_to_initial_state()` возвращает Source с `id=self.id`. `source_repo.update_source()` — UPDATE, не DELETE+INSERT.

## Файлы на диске

Файлы (аудио, скриншоты) не удаляются при reprocessing — только DB-записи. Reconcile чистит orphan-файлы при старте, но к этому моменту enrichment уже восстановлен и файлы снова привязаны к candidates. Копировать файлы не нужно — пути остаются валидными.

Edge case: если процесс упал между транзакцией 1 и транзакцией 2, при следующем старте reconcile удалит orphan-файлы (candidates нет → файлы осиротели). Enrichment cache тоже очистится. Это приемлемо — данные expendable, как было до этой фичи.

## Known limitations

- **Кастомные context_fragment:** если пользователь отредактировал фразу вручную (`has_custom_context_fragment=True`), при reprocessing pipeline сгенерирует оригинальный `context_fragment`. Побайтовое совпадение не сработает — enrichment потеряется. Это осознанное ограничение: matching должен быть строгим.

## Cleanup при старте

В reconcile (`database.py`): `enrichment_cache_repo.cleanup_all()`. Любые остатки после краша удаляются безусловно. Данные expendable.

## Где в коде

- **Порт:** `domain/ports/enrichment_cache_repository.py` — ABC с `save_from_source`, `restore_to_candidates`, `cleanup`, `cleanup_all`
- **Реализация:** `infrastructure/persistence/sqla_enrichment_cache_repository.py` — SQL JOIN'ы, INSERT INTO SELECT, ON CONFLICT REPLACE
- **Модель:** `infrastructure/persistence/models.py` — SQLAlchemy model для `enrichment_cache`
- **Use case:** `application/use_cases/reprocess_source.py` — `execute()` вызывает `save_from_source` + delete + reset; `finalize()` вызывает restore + cleanup в savepoint (best-effort)
- **Route:** `infrastructure/api/routes/sources.py` — тонкая обёртка: `execute()` → commit → `_process_background` → `process_source.execute()` → `finalize()` (новый экземпляр use case с bg_session) → commit
- **Миграция:** новая Alembic-миграция для `enrichment_cache`
- **Reconcile:** `database.py` — вызвать `cleanup_all()` при старте
- **DI:** `infrastructure/container.py` — `ReprocessSourceUseCase` получает `EnrichmentCacheRepository` через конструктор
