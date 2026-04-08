# Spec 2 — Экспонировать `anki_field_image` / `anki_field_audio` в настройки

**Дата:** 2026-04-08
**Статус:** утверждено

## Цель

Баг-фикс: настройки имён Anki-полей для изображений и аудио (`anki_field_image`, `anki_field_audio`) используются в `sync_to_anki`, но не экспонированы в `SettingsDTO` / API / UI. Пользователь не может их поменять. Плюс — `ensure_note_type` не добавляет недостающие поля к уже существующему note type, из-за чего у пользователей со старыми инсталляциями в AnythingToAnkiType могут отсутствовать поля Image/Audio.

## Критерий приёмки

Если у кандидата есть связанные `screenshot_path` и/или `audio_path`, после sync в Anki они попадают в поля, имена которых заданы в настройках. По умолчанию — `"Image"` и `"Audio"`. У существующих инсталляций, где AnythingToAnkiType создан без Image/Audio, эти поля добавляются автоматически при первом `ensure_note_type`.

## Контекст кода

- `backend/application/use_cases/sync_to_anki.py` уже читает ключи `anki_field_image` / `anki_field_audio` из `settings_repo`, с дефолтами `"Image"` / `"Audio"`, и формирует note-поля для media
- `backend/application/dto/settings_dtos.py` → `SettingsDTO` и `UpdateSettingsRequest` не содержат этих полей
- `backend/application/use_cases/manage_settings.py` — не читает/пишет эти ключи
- `backend/domain/ports/anki_connector.py` → `ensure_note_type(model_name, fields)` — сейчас реализация `anki_connect_connector.ensure_note_type` возвращается сразу, если модель уже существует, и не добавляет недостающие поля
- `SettingsPage.tsx` — нет инпутов для этих полей
- `api/types.ts` — нет полей в типе `Settings`

## Архитектура изменений

### Domain

Контракт `AnkiConnector.ensure_note_type(model_name, fields)` уточняется:
- Если note type отсутствует — создать с указанным набором полей (как сейчас)
- Если существует — **гарантировать**, что у него есть все поля из `fields`; отсутствующие добавить через AnkiConnect action `modelFieldAdd`
- Лишние поля не удалять

### Infrastructure

`backend/infrastructure/adapters/anki_connect_connector.py` — переписать `ensure_note_type`:

```
def ensure_note_type(self, model_name: str, fields: list[str]) -> None:
    existing_models = self._invoke("modelNames")
    if model_name not in existing_models:
        self._invoke("createModel", ...)  # как сейчас
        return
    current_fields = self._invoke("modelFieldNames", modelName=model_name)
    for idx, field in enumerate(fields):
        if field not in current_fields:
            self._invoke(
                "modelFieldAdd",
                modelName=model_name,
                fieldName=field,
                index=idx,
            )
```

### Application

`backend/application/dto/settings_dtos.py`:
- В `SettingsDTO` добавить `anki_field_image: str`, `anki_field_audio: str`
- В `UpdateSettingsRequest` — то же как `| None = None`

`backend/application/use_cases/manage_settings.py`:
- `get_settings()` — читать ключи `anki_field_image`/`anki_field_audio` с дефолтами `"Image"`/`"Audio"`
- `update_settings()` — записывать новые ключи если переданы

**Важно:** поля Image/Audio **не** обязательные в смысле `verify_note_type.required_fields`. Их не добавляем в `required_fields` — не все источники генерируют медиа, и пользователь может иметь кастомный note type без этих полей. Семантика остаётся: пусто в настройках → не отправлять; непусто + файл существует → отправлять.

### Frontend

`frontends/web/src/api/types.ts`:
- В `Settings` добавить `anki_field_image: string`, `anki_field_audio: string`
- В `UpdateSettingsRequest` — то же, необязательные

`frontends/web/src/pages/SettingsPage.tsx`:
- Добавить два текстовых поля «Anki Image field» и «Anki Audio field» в секцию Anki-настроек

## Тесты

### Unit

- `tests/unit/application/test_manage_settings.py`:
  - `get_settings` возвращает `anki_field_image = "Image"` и `anki_field_audio = "Audio"` при пустом репозитории
  - `update_settings` сохраняет новые значения
- `tests/unit/application/test_sync_to_anki.py`:
  - Кандидат с media и непустыми настройками → note содержит поля Image/Audio с правильным контентом
  - Кандидат без media → поля Image/Audio не включены в note
  - Пустая настройка `anki_field_image` → поле не включено даже при наличии media

### Integration

- `tests/integration/test_api_settings.py`:
  - PUT `/api/settings` с новыми полями → GET возвращает их
- Интеграционный тест на `AnkiConnectConnector.ensure_note_type`:
  - Note type существует с полями `[Sentence, Target]` → вызов с `[Sentence, Target, Image]` добавляет `Image` → `modelFieldNames` возвращает все три

## Миграция БД

Не требуется — настройки хранятся в key-value таблице `settings`, ключи уже используются и могут отсутствовать (дефолты читаются из кода).

## Порядок работ в плане

1. Расширить `AnkiConnector.ensure_note_type` поведение: добавлять недостающие поля к существующему note type
2. Добавить тесты на `ensure_note_type` (integration/stub)
3. Расширить `SettingsDTO`, `UpdateSettingsRequest`
4. Обновить `ManageSettingsUseCase` чтение/запись новых ключей
5. Тесты `test_manage_settings`, `test_api_settings`
6. Расширить тип `Settings` в `api/types.ts`
7. Добавить поля в UI `SettingsPage.tsx`
8. Прогон тестов + `tsc -b`
9. Проверить вручную: создать кандидата с media, запустить sync → в Anki есть картинка/аудио

## Выход за рамки

- Не меняем `verify_note_type.required_fields` — Image/Audio остаются опциональными для note type
- Не меняем `sync_to_anki` логику формирования note-полей для media (она уже корректна)
- Не трогаем другие настройки
