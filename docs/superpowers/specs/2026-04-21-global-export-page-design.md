# Global Export Page — Design Spec

**Дата:** 2026-04-21
**Задача:** Общая страница export — из всех источников

## Цель

Одной кнопкой залить в Anki всё накопленное из всех источников, без прыганья по каждому отдельно. Глобальная страница показывает все "learn" карточки, сгруппированные по источникам с заголовками.

## Backend

### API Endpoints

Старые per-source ручки (`/sources/{source_id}/cards`, `/sources/{source_id}/sync-to-anki`) убираются. Новые:

| Метод | Endpoint | Поведение |
|-------|----------|-----------|
| GET | `/export/cards` | Все "learn" карточки, сгруппированные по source → `GlobalExportDTO` |
| GET | `/export/cards/{source_id}` | То же, один источник → `GlobalExportDTO` (одна секция) |
| POST | `/export/sync-to-anki` | Синк всех источников в Anki → `SyncResultDTO` (агрегированный) |
| POST | `/export/sync-to-anki/{source_id}` | Синк одного источника → `SyncResultDTO` |

Ответ всегда `GlobalExportDTO` для GET — даже для одного source возвращается одна секция. Фронтенд работает с единым форматом.

Остальные ручки без изменений: `/anki/status`, `/anki/verify-note-type`, `/anki/create-note-type`, `/anki/templates`.

### DTO

Новые:

```python
class ExportSectionDTO(BaseModel):
    source_id: int
    source_title: str
    cards: list[CardPreviewDTO]

class GlobalExportDTO(BaseModel):
    sections: list[ExportSectionDTO]
```

Pydantic `BaseModel` — по конвенции проекта (`pydantic` для `application/dto`).

`CardPreviewDTO` и `SyncResultDTO` — без изменений.

### Repository

Новый метод в порту `CandidateRepository`:

```python
def get_all_by_status(self, status: CandidateStatus) -> list[StoredCandidate]: ...
```

Универсальный метод с фильтром по статусу. Существующий `get_by_source` не трогаем.

`SourceRepository` — уже есть `list_all()`, новых методов не нужно.

### Use Cases

**`GetExportCardsUseCase`** — заменяет `GetSourceCardsUseCase`:
- `execute(source_id: int) -> GlobalExportDTO` — один источник (одна секция)
- `execute_all() -> GlobalExportDTO` — все источники
- Логика построения `CardPreviewDTO` из кандидата — общий приватный метод, не дублируется
- Для `execute_all()`: вызывает `candidate_repo.get_all_by_status(CandidateStatus.LEARN)`, группирует по `source_id`, подтягивает названия через `source_repo`

**`SyncToAnkiUseCase`** — расширяется:
- `execute(source_id: int) -> SyncResultDTO` — как сейчас
- `execute_all() -> SyncResultDTO` — итерирует по всем source_id с learn-кандидатами, агрегирует результат

## Frontend

### Рефакторинг: выделение CardList

Из `ExportPage.tsx` выносится:
- `CardPreviewItem` → `components/CardList.tsx`
- Новый компонент `CardList`: принимает `cards: CardPreview[]`, `generatingIds`, `onGenerate`. Рендерит список `CardPreviewItem`. Чистая презентация.

### ExportPage (per-source)

Путь: `/sources/:id/export`

- Использует `CardList` для отображения
- Загружает данные через `GET /export/cards/{source_id}`
- Sync через `POST /export/sync-to-anki/{source_id}`
- Без изменений в поведении

### GlobalExportPage (новый)

Путь: `/export`

- Загружает данные через `GET /export/cards`
- Рендерит секции: для каждого source — заголовок с названием источника + счётчик карточек + `CardList`
- Секции разделены визуально (divider)
- Сверху: общий счётчик карточек + "Generate All" + Anki status
- Внизу: одна кнопка "Add to Anki · N cards" → `POST /export/sync-to-anki`
- Пустое состояние: «No words marked for learning»

### Роутинг

```
/export           → GlobalExportPage
/sources/:id/export → ExportPage
```

### API Client

Новые методы в `client.ts`:

```typescript
getExportCards: () => GlobalExportDTO
getExportCardsBySource: (sourceId: number) => GlobalExportDTO
syncAllToAnki: () => SyncResult
syncToAnki: (sourceId: number) => SyncResult
```

### Типы

Новые в `types.ts`:

```typescript
interface ExportSection {
  source_id: number
  source_title: string
  cards: CardPreview[]
}

interface GlobalExport {
  sections: ExportSection[]
}
```

## Scope

**В scope:**
- Новые API endpoints (`/export/cards`, `/export/sync-to-anki` ± `/{source_id}`)
- Новый `GetExportCardsUseCase` (замена `GetSourceCardsUseCase`)
- Расширение `SyncToAnkiUseCase` методом `execute_all()`
- Новый метод `get_all_by_status()` в `CandidateRepository`
- Выделение `CardList` из `ExportPage`
- Новый `GlobalExportPage`
- Миграция `ExportPage` на новые endpoints
- Удаление старых endpoints

**Вне scope:**
- Фильтрация по CEFR/тегам/типу
- Per-source кнопки sync на глобальной странице
- Изменения в review flow
