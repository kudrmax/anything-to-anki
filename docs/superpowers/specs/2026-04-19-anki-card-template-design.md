# Anki Card Template — дизайн

## Проблема

1. Шаблоны карточек Anki захардкожены в `anki_connect_connector.py` — минимальные, без стилей, без половины полей (Audio, Image, Examples, Translation, Synonyms)
2. Файлы `anki-templates/` лежат мёртвым грузом — нигде в коде не используются
3. Нет способа скопировать актуальный шаблон из UI
4. Image, Audio, Examples в шаблонах не стилизованы (голые теги, `<br><br>` вместо CSS-отступов)

## Решение

### 1. Шаблоны — единый источник правды

Файлы `anki-templates/front.html`, `back.html`, `style.css` — каноничные шаблоны. Хранятся с плейсхолдерами вместо конкретных имён полей Anki.

**Плейсхолдеры:**

| Плейсхолдер | Настройка | Дефолт |
|---|---|---|
| `%FIELD_SENTENCE%` | `anki_field_sentence` | Sentence |
| `%FIELD_TARGET%` | `anki_field_target_word` | Target |
| `%FIELD_MEANING%` | `anki_field_meaning` | Meaning |
| `%FIELD_IPA%` | `anki_field_ipa` | IPA |
| `%FIELD_IMAGE%` | `anki_field_image` | Image |
| `%FIELD_AUDIO%` | `anki_field_audio` | Audio |
| `%FIELD_TRANSLATION%` | `anki_field_translation` | Translation |
| `%FIELD_SYNONYMS%` | `anki_field_synonyms` | Synonyms |
| `%FIELD_EXAMPLES%` | `anki_field_examples` | Examples |

Формат `%FIELD_X%` выбран чтобы не конфликтовать с Anki mustache-синтаксисом `{{...}}`.

### 2. Исправления шаблонов

**Front (`front.html`):**
```html
<div class="card-inner">
  <div class="sentence">{{edit:%FIELD_SENTENCE%}}</div>
  {{#%FIELD_IMAGE%}}<div class="image">{{%FIELD_IMAGE%}}</div>{{/%FIELD_IMAGE%}}
  {{#%FIELD_AUDIO%}}<div class="audio">{{%FIELD_AUDIO%}}</div>{{/%FIELD_AUDIO%}}
</div>
```

Image вынесена на переднюю сторону. Audio остаётся на фронте (как в текущем шаблоне).

**Back (`back.html`):**
```html
<div class="card-inner">
  <div class="sentence">{{edit:%FIELD_SENTENCE%}}</div>

  {{#%FIELD_IMAGE%}}<div class="image">{{%FIELD_IMAGE%}}</div>{{/%FIELD_IMAGE%}}
  {{#%FIELD_AUDIO%}}<div class="audio">{{%FIELD_AUDIO%}}</div>{{/%FIELD_AUDIO%}}

  <hr>

  <div class="target-word">{{edit:%FIELD_TARGET%}}</div>
  {{#%FIELD_IPA%}}<div class="ipa">{{edit:%FIELD_IPA%}}</div>{{/%FIELD_IPA%}}

  <hr>

  <div class="meaning">{{edit:%FIELD_MEANING%}}</div>

  {{#%FIELD_TRANSLATION%}}<div class="translation">{{%FIELD_TRANSLATION%}}</div>{{/%FIELD_TRANSLATION%}}
  {{#%FIELD_SYNONYMS%}}<div class="synonyms">{{%FIELD_SYNONYMS%}}</div>{{/%FIELD_SYNONYMS%}}

  <hr>

  {{#%FIELD_EXAMPLES%}}<div class="examples">{{%FIELD_EXAMPLES%}}</div>{{/%FIELD_EXAMPLES%}}
</div>
```

**CSS (`style.css`) — новые/изменённые классы:**

```css
/* Image */
.image img {
  max-width: 100%;
  border-radius: 8px;
  margin-top: 12px;
}

/* Audio */
.audio {
  margin-top: 8px;
}

/* Translation */
.translation {
  font-size: 16px;
  color: #78716c;
  margin-top: 8px;
  font-style: italic;
}

/* Synonyms */
.synonyms {
  font-size: 15px;
  color: #78716c;
  margin-top: 6px;
}

/* Examples */
.examples {
  font-size: 15px;
  color: #5c4033;
  line-height: 1.6;
  padding: 12px 16px;
  background: rgba(0,0,0,0.03);
  border-radius: 8px;
  border-left: 3px solid #e8ddd0;
}
```

Плюс nightMode-варианты для всех новых классов.

CSS не содержит плейсхолдеров — в нём нет имён полей Anki, только CSS-классы.

### 3. Backend — рендеринг шаблонов

Новая утилита `backend/src/backend/application/utils/anki_template_renderer.py`:

- Читает файлы `anki-templates/{front.html,back.html,style.css}`
- Принимает маппинг `{placeholder: field_name}`
- Возвращает строки с подставленными именами полей

Маппинг строится из настроек пользователя (`anki_field_*` из таблицы settings).

### 4. Connector — интеграция

Удаляются константы `_FRONT_TEMPLATE`, `_BACK_TEMPLATE`, `_CARD_CSS`.

Метод `ensure_note_type` получает отрендеренные шаблоны (front, back, css) как параметры. Вызывающий код (use case `sync_to_anki`) рендерит шаблоны через утилиту и передаёт в connector.

Обновление шаблона в существующей модели — только вручную через кнопки копирования.

### 5. API endpoint

`GET /api/anki/templates` — возвращает `{front: str, back: str, css: str}` с подставленными именами полей из текущих настроек.

### 6. Frontend — Settings UI

В разделе Anki на `SettingsPage` — блок **"Card Template"** с тремя кнопками:
- **Copy Front** — копирует front-шаблон в буфер
- **Copy Back** — копирует back-шаблон в буфер
- **Copy CSS** — копирует CSS в буфер

Кнопки вызывают `GET /api/anki/templates` и копируют соответствующую часть. При успехе — короткое уведомление "Copied!".

## Что НЕ входит в scope

- Автоматическое обновление шаблона в существующей Anki-модели при синке
- Предпросмотр карточки в UI
- Редактирование шаблонов в UI
