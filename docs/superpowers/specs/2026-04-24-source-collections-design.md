# Source Collections — Design Spec

## Summary

Добавить сущность **Collection** для группировки источников. Один источник принадлежит максимум одной коллекции (опционально). Цель — организация: объединить серии сериала в сериал, главы книги в книгу.

Scope этой задачи — только группировка и UI. Anki-интеграция (проброс тегов в карточки) — отдельная задача.

---

## Domain Layer

### Entity: Collection

`backend/src/backend/domain/entities/collection.py`

```python
@dataclass(frozen=True)
class Collection:
    name: str
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
```

Инварианты:
- `name` — непустая строка, max 200 символов, уникальна среди всех коллекций.

### Entity: Source — изменения

Добавить поле `collection_id: int | None = None` в существующий `Source` dataclass.

### Port: CollectionRepository

`backend/src/backend/domain/ports/collection_repository.py`

```python
class CollectionRepository(ABC):
    @abstractmethod
    def create(self, collection: Collection) -> Collection: ...

    @abstractmethod
    def get_by_id(self, collection_id: int) -> Collection | None: ...

    @abstractmethod
    def list_all(self) -> list[Collection]: ...

    @abstractmethod
    def rename(self, collection_id: int, new_name: str) -> Collection: ...

    @abstractmethod
    def delete(self, collection_id: int) -> None: ...
```

---

## Application Layer

### Use Cases

| Use Case | Input | Output | Логика |
|---|---|---|---|
| `CreateCollectionUseCase` | `name: str` | `CollectionDTO` | Валидация имени (не пустое, ≤200, уникальное). Создание через repository. |
| `ListCollectionsUseCase` | — | `list[CollectionDTO]` | Возвращает все коллекции с `source_count`. Сортировка по `name` ASC. |
| `RenameCollectionUseCase` | `collection_id: int, new_name: str` | `CollectionDTO` | Валидация нового имени (не пустое, ≤200, уникальное). |
| `DeleteCollectionUseCase` | `collection_id: int` | `None` | Удаляет коллекцию. Источники с этим `collection_id` получают `collection_id = NULL` (ON DELETE SET NULL на уровне БД). |
| `AssignSourceToCollectionUseCase` | `source_id: int, collection_id: int \| None` | `SourceDTO` | Назначает или снимает (`None`) коллекцию у источника. |

### DTO

```python
class CollectionDTO(BaseModel):
    id: int
    name: str
    source_count: int
    created_at: datetime
```

### Изменения в существующих DTO

`SourceDTO` — добавить:
```python
collection_id: int | None = None
collection_name: str | None = None
```

### Изменения в существующих Use Cases

`GetSourcesUseCase.list_all()` — добавить опциональный параметр `collection_id: int | None = None` для фильтрации. При `collection_id is not None` — возвращать только источники этой коллекции.

---

## Infrastructure Layer

### Database

**Alembic migration** — новая таблица + колонка:

```sql
CREATE TABLE collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE sources ADD COLUMN collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL;
```

**SQLAlchemy model** — `CollectionModel` в `models.py`:
- Поля: `id`, `name`, `created_at`
- Relationship: `sources` (one-to-many)

**SourceModel** — добавить:
- `collection_id = Column(Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)`

### Repository: SqliteCollectionRepository

`backend/src/backend/infrastructure/persistence/collection_repository.py`

Реализация `CollectionRepository`. Метод `list_all()` делает LEFT JOIN с подсчётом `source_count`.

### API Endpoints

Новый роутер: `backend/src/backend/infrastructure/api/routes/collections.py`

| Method | Endpoint | Use Case | Body/Params |
|---|---|---|---|
| `POST` | `/api/collections` | `CreateCollectionUseCase` | `{ "name": "Breaking Bad" }` |
| `GET` | `/api/collections` | `ListCollectionsUseCase` | — |
| `PATCH` | `/api/collections/{id}` | `RenameCollectionUseCase` | `{ "name": "New Name" }` |
| `DELETE` | `/api/collections/{id}` | `DeleteCollectionUseCase` | — |

Назначение коллекции источнику — новый endpoint на существующем роутере sources:

| Method | Endpoint | Use Case | Body |
|---|---|---|---|
| `PATCH` | `/api/sources/{id}/collection` | `AssignSourceToCollectionUseCase` | `{ "collection_id": 5 }` или `{ "collection_id": null }` |

Фильтрация — расширение существующего endpoint:

`GET /api/sources?collection_id=5` — добавить query parameter в `list_sources()`.

### DI Container

Зарегистрировать в `container.py`:
- `CollectionRepository` → `SqliteCollectionRepository`
- Все новые use cases

---

## Frontend

### Принципы

- **Бизнес-логика — ноль.** Frontend только: рендерит данные, отправляет API-запросы, управляет локальным UI-state.
- **Стили — из существующего приложения.** Не создавать новые стилевые решения. Использовать существующие компоненты, цвета, border-radius, spacing, шрифты из текущей темы.

### API Client

Добавить в `client.ts`:
- `getCollections(): Promise<CollectionDTO[]>`
- `createCollection(name: string): Promise<CollectionDTO>`
- `renameCollection(id: number, name: string): Promise<CollectionDTO>`
- `deleteCollection(id: number): Promise<void>`
- `assignSourceCollection(sourceId: number, collectionId: number | null): Promise<SourceDTO>`

Расширить `getSources()` — опциональный `collectionId` query param.

### Types

Добавить в `types.ts`:
```typescript
interface Collection {
  id: number;
  name: string;
  source_count: number;
  created_at: string;
}
```

Расширить `Source`:
```typescript
collection_id: number | null;
collection_name: string | null;
```

### UI: InboxPage

**Filter chips** — горизонтальная полоса чипсов над списком источников:
- Чип «All (N)» — всегда первый, показывает все источники.
- Чип для каждой коллекции — `{name} ({source_count})`. Клик → фильтрация через `GET /sources?collection_id=X`.
- Чип «+ New» — в конце ряда. Клик → inline input для имени → POST `/api/collections`.
- Right-click на чипсе коллекции → контекстное меню:
  - **Rename** → inline input с текущим именем → PATCH `/api/collections/{id}`.
  - **Delete collection** → диалог подтверждения («N sources will become uncategorized») → DELETE `/api/collections/{id}`.

**SourceCard** — бейдж коллекции:
- Если источник в коллекции — отображается бейдж с именем коллекции.
- Клик на бейдж (или на место бейджа если нет коллекции) → dropdown со списком коллекций + «No collection».
- Выбор → PATCH `/api/sources/{id}/collection`.

---

## Тестирование

### Backend

**Unit tests (use cases):**
- `CreateCollectionUseCase`: создание, дубль имени → ошибка, пустое имя → ошибка
- `RenameCollectionUseCase`: rename, дубль → ошибка, несуществующий ID → ошибка
- `DeleteCollectionUseCase`: удаление, проверка что sources получили `collection_id = None`
- `AssignSourceToCollectionUseCase`: назначение, снятие, несуществующий source/collection → ошибка
- `ListCollectionsUseCase`: пустой список, несколько коллекций с корректными `source_count`
- `GetSourcesUseCase.list_all(collection_id=X)`: фильтрация работает

**Integration tests:**
- Полный цикл: create collection → assign sources → rename → delete → verify sources intact with `collection_id = None`

### Frontend

- Ручная проверка в браузере через dev server: все 5 сценариев из мокапов (создание, назначение, переименование, удаление, фильтрация).

---

## Не в scope

- Anki-теги (проброс collection → Anki tag при экспорте) — отдельная задача
- Иерархия коллекций — не планируется
- Множественные коллекции на источник — не планируется
- Отдельный экран управления коллекциями — управление через чипсы на InboxPage
