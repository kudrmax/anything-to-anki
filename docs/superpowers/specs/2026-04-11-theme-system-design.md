# Theme System Design

## Решение

Добавить систему тем с переключателем. Три темы на старте:

1. **Legacy Cosmic** (текущая) — glass-morphism, mesh-градиенты, индиго+циан
2. **Liquid Glass** (новая) — iOS 26 style, frosted glass с specular highlights, capsule controls, iOS system colors, dark only
3. **Book** (новая) — serif (Georgia), землистые тона, золотой акцент, italic-фрагменты, pill-кнопки, dark only

## Архитектура

### Подход: CSS Custom Properties + data-attribute

Тема переключается через `data-theme` атрибут на `<html>`:

```html
<html data-theme="cosmic">  <!-- или "liquid-glass", "book" -->
```

Каждая тема опреде��яет набор CSS custom properties в `index.css`:

```css
[data-theme="cosmic"] { --bg: #0c0e18; --text: #eef0ff; ... }
[data-theme="liquid-glass"] { --bg: #050508; --text: #f5f5f7; ... }
[data-theme="book"] { --bg: #1c1917; --text: #e7e5e4; ... }
```

### Что определяет тема (design tokens)

**Surfaces:**
- `--bg` — основной фон приложения
- `--surface` — фон карточек
- `--surface-marked` — фон отмеченных карточек
- `--surface-hover` — ховер-состояние
- `--header-bg` — фон toolbar

**Text:**
- `--text` — основной текст
- `--text-muted` — вторичный текст
- `--text-disabled` — disabled/placeholder

**Accent:**
- `--accent` — primary accent color
- `--accent-bg` — фон accent-элементов (кнопки, pills)
- `--accent-border` — бордер accent-элементов

**Borders:**
- `--border` — основная граница
- `--border-subtle` — тонкая граница

**Status colors (общие для всех тем):**
- `--learn` / `--learn-bg` / `--learn-border`
- `--know` / `--know-bg` / `--know-border`
- `--skip` / `--skip-bg` / `--skip-border`

**Shape:**
- `--radius-card` — скругление карточек
- `--radius-btn` — скругление кнопок
- `--radius-pill` — скругление pills/chips

**Effects (опционально, per-theme):**
- `--blur` — backdrop-filter
- `--shadow` — box-shadow карточек

**Typography (per-theme, Book отличается):**
- `--font-body` — шрифт для текста
- `--font-ui` — шрифт для UI-элементов

### Что НЕ меняется между темами

- Layout (40%/60% split, toolbar structure)
- Компоненты (те же React-компоненты, те же props)
- Бизнес-логика
- API

### Переключатель тем

Местоположение: Settings page (уже есть `/settings`).
Сохранение: `localStorage` (через `lib/preferences.ts`, паттерн уже используется для `sortOrder`).
Применение: при загрузке читаем из localStorage, ставим `data-theme` на `<html>`.

### Liquid Glass — специфика

Библиотека `liquid-glass-react` для displacement/refraction эффектов на карточках.
Fallback для Safari/Firefox: обычный `backdrop-filter: blur()` без displacement.

Специфичные CSS-свойства (только для liquid-glass):
- Ambient color blobs (absolute-positioned radial gradients)
- Specular highlights (`::after` pseudo-element на карточках)
- Capsule shapes (border-radius: 100px на кнопках)
- 0.5px hairline borders
- `backdrop-filter: blur(40px) saturate(180%)`
- iOS system colors: `#0a84ff`, `#30d158`, `#ff453a`, `#ff9f0a`

### Book — специфика

- `font-family: Georgia, serif` для текста (Inter для UI-элементов)
- Italic фрагменты
- Gold accent `#d6a756`
- Pill buttons с обводкой (`border-radius: 20px`)
- UPPERCASE labels с letter-spacing
- Тёплые землистые тона (#1c1917, #231f1b, #2c2520)

## План реализации

### Шаг 1: Архитектура тем

1. Определить все CSS custom properties (design tokens) в `index.css`
2. Рефакторнуть текущие стили из inline `style=` и CSS variables в единую систему tokens
3. Обернуть текущий дизайн в `[data-theme="cosmic"]`
4. Добавить переключатель в Settings + persistence в localStorage
5. Применение темы в `main.tsx` при загрузке

### Шаг 2: Liquid Glass

1. `npm install liquid-glass-react`
2. Определить `[data-theme="liquid-glass"]` tokens
3. Добавить ambient blobs компонент (условно рендерится только для liquid-glass)
4. Добавить specular highlight styles (условный CSS)
5. Обернуть карточки в `<LiquidGlass>` когда тема = liquid-glass
6. Fallback для Safari/Firefox

### Шаг 3: Book

1. Подключить Google Fonts Georgia (или системный)
2. Определить `[data-theme="book"]` tokens
3. Специфичные стили: italic fragments, uppercase labels, pill buttons
4. Тёплая землистая палитра

## Визуальные референсы

Мокапы всех тем: `tmp/theme-mockups.html`
