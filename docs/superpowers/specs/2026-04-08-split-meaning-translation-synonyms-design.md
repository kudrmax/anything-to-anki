# Spec 3 — Разделить Meaning на Meaning / Translation / Synonyms

**Дата:** 2026-04-08
**Статус:** утверждено
**Зависит от:** Spec 1 (prompts-to-yaml-config), Spec 2 (anki-image-audio-settings)

## Цель

Сейчас AI возвращает одно текстовое поле `meaning`, внутри которого четыре строки: определение, контекст, русский перевод, синонимы. Это неудобно и смешивает семантически разные данные. Разделить ответ на три структурированных поля: `meaning`, `translation`, `synonyms` (IPA остаётся как было). Поля сохраняются в БД, отображаются в UI раздельно и отправляются в Anki в отдельные поля note type.

## Требования

- AI возвращает JSON с полями `meaning`, `translation`, `synonyms`, `ipa` — все обязательные на уровне AI-схемы
- Domain entity `CandidateMeaning` хранит новые поля как `str | None` (nullable для совместимости со старыми записями)
- БД-миграция добавляет `translation TEXT NULL`, `synonyms TEXT NULL` в `candidate_meanings`, **не трогая** старые записи (их `meaning` остаётся как есть — единый текст)
- UI `CandidateCardV2` показывает Meaning крупно, ниже Translation с иконкой, ниже Synonyms с иконкой (иконки из `lucide-react`, не эмодзи)
- Sync в Anki: translation и synonyms обязательны в note type, настройки `anki_field_translation`/`anki_field_synonyms` имеют дефолты `"Translation"`/`"Synonyms"`, входят в `verify_note_type.required_fields`
- Для AnythingToAnkiType поля Translation/Synonyms создаются автоматически через расширенный `ensure_note_type` (из Spec 2)
- Для старых записей с `translation = NULL` / `synonyms = NULL`: при формировании note-словаря соответствующие ключи **не включаются** (в Anki поле остаётся пустым — без пустых строк)

## Конфиг промпта

`config/prompts.yaml` — расширяется новыми секциями:

```yaml
ai:
  generate_meaning:
    user_template: ...
    system:
      intro: ...         # без изменений из Spec 1
      meaning: |
        <текущий блок meaning из Spec 1, но БЕЗ строк LINE 3 и LINE 4;
        LINE 1 (Definition) и LINE 2 (Context explanation) остаются
        дословно, нумерация сохраняется — минимальное редактирование>
      translation: |
        For the 'translation' field, provide a short Russian translation (1–3 words).
        Short, natural — not a dictionary entry.
      synonyms: |
        For the 'synonyms' field, provide 2–3 English synonyms or short phrases
        for the specific meaning used in context.
      ipa: ...           # без изменений из Spec 1
```

**Правило переноса:** тексты translation/synonyms берём из LINE 3 / LINE 4 текущего промпта (после Spec 1), механически, не переписывая. Меняется только адресация («LINE 3 …» → «For the 'translation' field …»).

`PromptsLoader` (из Spec 1) расширяется: читает новые секции, склеивает в порядке `intro + meaning + translation + synonyms + ipa`. В `PromptsConfig` поле `generate_meaning_system` остаётся одной склеенной строкой — структура value object не меняется.

## AI-адаптер

`backend/infrastructure/adapters/claude_ai_service.py`:

`_SINGLE_SCHEMA`:
```python
{
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "meaning": {"type": "string"},
            "translation": {"type": "string"},
            "synonyms": {"type": "string"},
            "ipa": {"type": "string"},
        },
        "required": ["meaning", "translation", "synonyms", "ipa"],
    },
}
```

`_BATCH_SCHEMA` — аналогично, внутри `items.properties`.

`_async_generate` и `_async_generate_batch` — возвращают `GenerationResult` / `BatchMeaningResult` с новыми полями.

## Domain

`backend/domain/value_objects/generation_result.py`:
```
@dataclass(frozen=True)
class GenerationResult:
    meaning: str
    translation: str
    synonyms: str
    ipa: str | None
    tokens_used: int
```

`backend/domain/value_objects/batch_meaning_result.py`:
```
@dataclass(frozen=True)
class BatchMeaningResult:
    word_index: int
    meaning: str
    translation: str
    synonyms: str
    ipa: str | None
```

`backend/domain/entities/candidate_meaning.py`:
```
@dataclass(frozen=True)
class CandidateMeaning:
    candidate_id: int
    meaning: str | None
    translation: str | None
    synonyms: str | None
    ipa: str | None
    status: EnrichmentStatus
    error: str | None
    generated_at: datetime | None
```

Поля nullable на уровне entity, т.к. старые записи не имеют translation/synonyms и status может быть FAILED / PENDING.

## Application

`backend/application/dto/ai_dtos.py`:
```
class GenerateMeaningResponseDTO(BaseModel):
    candidate_id: int
    meaning: str
    translation: str
    synonyms: str
    ipa: str | None = None
    tokens_used: int
```

`backend/application/use_cases/generate_meaning.py`:
- Сохранять новые поля в `CandidateMeaning(...)` при upsert

`backend/application/use_cases/run_generation_job.py` (batch pipeline):
- Прокидывать translation/synonyms из `BatchMeaningResult` в entity

## Persistence

`backend/infrastructure/persistence/models.py` → `CandidateMeaningModel`:
- `translation: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `synonyms: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `to_entity()` / `from_entity()` включают новые поля

`backend/infrastructure/persistence/sqla_candidate_meaning_repository.py`:
- Upsert читает/пишет новые поля

### Alembic

Новая ревизия `0008_add_translation_synonyms.py`:
- `ALTER TABLE candidate_meanings ADD COLUMN translation TEXT`
- `ALTER TABLE candidate_meanings ADD COLUMN synonyms TEXT`

Старые записи остаются с `NULL` в новых колонках. Перегенерация не требуется.

## Sync to Anki

`backend/application/use_cases/sync_to_anki.py`:

Добавляются настройки:
```
field_translation = settings_repo.get("anki_field_translation", "Translation") or "Translation"
field_synonyms = settings_repo.get("anki_field_synonyms", "Synonyms") or "Synonyms"
```

`active_fields` расширяется — `field_translation` и `field_synonyms` всегда присутствуют (дефолты непустые). Для AnythingToAnkiType `ensure_note_type` вызывается автоматически (существующая ветка `if note_type == _DEFAULT_NOTE_TYPE`) и благодаря Spec 2 добавит недостающие Translation/Synonyms к уже существующей модели. Для кастомного note type пользователь сам обязан обеспечить наличие полей — при их отсутствии AnkiConnect вернёт ошибку, а кнопка «Verify» покажет missing fields.

Формирование note dict:
```python
if field_translation and candidate.meaning and candidate.meaning.translation:
    note[field_translation] = candidate.meaning.translation
if field_synonyms and candidate.meaning and candidate.meaning.synonyms:
    note[field_synonyms] = candidate.meaning.synonyms
```

Если настройка пуста → ключ пропущен (как и для других полей). Если значение в enrichment'е `None` (старая запись) → ключ пропущен, поле в карточке остаётся пустым. Пустые строки в Anki не шлём.

## Verify note type

Расширить `required_fields` в use case, где формируется запрос `VerifyNoteTypeRequest` (и в UI «проверить тип»): включить `field_translation` и `field_synonyms`. Пустые настройки в список не попадают (как и для остальных обязательных полей).

Найти место вызова:
- `backend/infrastructure/api/routes/` — роут `verify_note_type` или use case проверки
- Frontend `SettingsPage.tsx` — кнопка «Verify» использует `verifyNoteType` из api client

`required_fields` собирается из текущих настроек. После добавления translation/synonyms в `SettingsDTO` они автоматически попадают в список, если кнопка «Verify» формирует `required_fields` из активных настроек.

## Settings

`backend/application/dto/settings_dtos.py`:
- `SettingsDTO`: `anki_field_translation: str`, `anki_field_synonyms: str`
- `UpdateSettingsRequest`: те же как `| None = None`

`backend/application/use_cases/manage_settings.py`:
- Read/write ключей `anki_field_translation` / `anki_field_synonyms`, дефолты `"Translation"` / `"Synonyms"`

## Frontend

`frontends/web/src/api/types.ts`:
- `CandidateMeaning` (или эквивалентный тип в UI): `translation: string | null`, `synonyms: string | null`
- `Settings`: `anki_field_translation: string`, `anki_field_synonyms: string`

`frontends/web/src/pages/SettingsPage.tsx`:
- Два новых текстовых поля «Anki Translation field» и «Anki Synonyms field»

`frontends/web/src/components/CandidateCardV2.tsx` (и `CandidateCard.tsx`, если ещё используется):
- Meaning + IPA — вверху, как сейчас
- Translation — ниже, компактной строкой, с иконкой `Languages` (или `Globe`) из `lucide-react` перед текстом
- Synonyms — ещё ниже, с иконкой `BookOpen` (или `Copy`) из `lucide-react`
- Если `translation === null` (старая запись) — блок не рендерится; аналогично synonyms
- Никаких эмодзи — только иконки из lucide-react

## Тесты

### Unit

- `tests/unit/domain/test_candidate_meaning.py` — новые поля
- `tests/unit/application/test_generate_meaning.py`:
  - AI возвращает все 4 поля → все сохраняются в `CandidateMeaning`
  - Response DTO содержит новые поля
- `tests/unit/application/test_sync_to_anki.py`:
  - Кандидат с полными полями → note содержит Translation/Synonyms
  - Кандидат со старым enrichment (`translation = None`, `synonyms = None`) → note **не** содержит эти ключи, sync не падает
  - Пустая настройка `anki_field_translation` → ключ не включён даже при наличии данных
- `tests/unit/application/test_manage_settings.py` — новые ключи

### Integration

- `tests/integration/test_sqla_candidate_meaning_repository.py` — персист/загрузка новых полей, обратная совместимость со старыми записями
- `tests/integration/test_api_settings.py` — новые ключи в GET/PUT

## Порядок работ в плане

1. Расширить `config/prompts.yaml` новыми секциями translation/synonyms
2. Обновить `PromptsLoader`: читать новые секции, порядок склейки
3. Обновить тесты loader
4. Расширить JSON schemas в `claude_ai_service.py` (single + batch)
5. Расширить `GenerationResult`, `BatchMeaningResult`, `CandidateMeaning`
6. Обновить `GenerateMeaningResponseDTO` и use case
7. Alembic-миграция + модель + репозиторий persistence
8. Расширить `SettingsDTO` / `UpdateSettingsRequest` / `ManageSettingsUseCase`
9. Обновить `SyncToAnkiUseCase` — чтение настроек, формирование note dict, `active_fields`
10. Обновить frontend: types, SettingsPage (поля), CandidateCard (рендер + иконки)
11. Прогон всех тестов + `tsc -b`
12. Ручная проверка: сгенерировать новый meaning, убедиться что все поля на месте; sync в Anki → карточка содержит все поля; старый кандидат sync'ается без ошибок, поля Translation/Synonyms пустые

## Критерии приёмки

- Новый meaning для кандидата содержит 4 непустых поля (meaning, translation, synonyms, ipa)
- UI показывает их раздельно с иконками lucide-react (не эмодзи)
- Sync в Anki кладёт значения в отдельные поля note type
- Старый enrichment (без translation/synonyms) не ломает sync и не отправляет пустые поля
- `verify_note_type` успешен только когда все 6 обязательных полей (Sentence, Target, Meaning, IPA, Translation, Synonyms) есть в note type
- Image/Audio поля не входят в required (по Spec 2)
- Все тесты проходят, `tsc -b` чистый
