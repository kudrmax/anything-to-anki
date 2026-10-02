# Жалобы на карточки

На экране ревью у каждой карточки есть флажок «Report a problem with this card»: быстрые причины (`REPORT_REASONS` в `application/use_cases/report_candidate.py`) или свой текст. Жалоба сохраняется в таблицу `card_reports` той копии, где нажата кнопка (обычно prod).

Жалоба хранит снимок карточки на момент жалобы: слово, фразу, частотность, CEFR, число незнакомых слов во фразе, фразовый ли глагол, источник — и текст источника по 300 символов до и после фразы (`text_before`, `text_after`), чтобы видеть, что отрезала граница. Внешних ключей нет — жалоба переживает переобработку и удаление источника.

## Как разбирать

- API: `GET /api/card-reports` — все жалобы, новые сверху.
- Напрямую, только чтение:

```bash
sqlite3 -readonly ../anything-to-anki-prod/data/app.db "select created_at, source_title, lemma, comment, text_before || '[' || context_fragment || ']' || text_after from card_reports order by id desc"
```

Группировать по `comment`, затем по признакам снимка (`zipf_frequency`, `fragment_unknown_count`, `is_phrasal_verb`).
