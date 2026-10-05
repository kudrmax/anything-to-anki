# Экспорт: готовые и неполные карточки

## Задача

У части карточек перед экспортом чего-то не хватает: нет meaning или озвучки фразы. Такие карточки не должны уходить в Anki незаметно. Исправлять их нужно на ревью, где уже есть все инструменты, а не одной кнопкой «догенерировать всё».

## Правило готовности

Карточка **готова**, если у неё есть:
- meaning (текст определения);
- **и** озвучка фразы: аудиоклип из видео **или** TTS.

Картинка и произношение US/UK на готовность не влияют.

Правило живёт в backend (domain). Фронт только показывает результат.

## Backend

- `domain/value_objects/missing_card_part.py`: `MissingCardPart` (`meaning`, `audio`).
- `domain/value_objects/export_group.py`: `ExportGroup` (`ready`, `incomplete`).
- `domain/services/export_readiness.py`: `missing_parts(candidate)` и `export_group(candidate)`.
- `ExportBatch` умеет отдавать pending-карточки одной группы.
- `GET /export/cards[/{source_id}]` → `GlobalExportDTO { ready: [section], incomplete: [section], exported_count }`. У карточки есть поле `missing: list[str]`.
- `POST /export/sync-to-anki[/{source_id}]?group=ready|incomplete` экспортирует только карточки указанной группы. Параметр обязательный.

## Frontend

- Экран экспорта показывает две группы: «Ready» и «Incomplete». У каждой группы своя кнопка экспорта: «Add to Anki · N» и «Export incomplete · N».
- В строке неполной карточки видно, чего не хватает.
- Клик по строке открывает эту карточку на ревью: `/sources/{id}/review?candidate={candidateId}`.
- Ревью читает `candidate` из URL и делает эту карточку текущей.

## Тесты

- Unit: правило готовности, группировка в `GetExportCardsUseCase`, фильтр группы в `SyncToAnkiUseCase`.
- Integration: API экспорта и синхронизации с параметром `group`.
