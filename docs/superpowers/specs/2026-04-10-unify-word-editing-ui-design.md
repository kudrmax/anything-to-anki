# Унификация UI редактирования границ и добавления слова

**Дата:** 2026-04-10

## Проблема

Два сценария — редактирование границ существующего target'а и ручное добавление нового слова — реализованы двумя отдельными компонентами (`SetContextPopover`, `SelectionPopover`) с разным визуалом, разными точками входа и дублированным кодом. Тулбар ReviewPage перегружен, элементы расположены нелогично.

## Scope

1. **Переработка тулбара ReviewPage** — один чистый ряд, убрано всё лишнее.
2. **Унификация поповеров** — один `TextSelectionPopover` с двумя режимами (`edit` / `add`).
3. **Новый flow «+ Add word»** — кнопка в тулбаре → баннер → выделение текста → поповер.
4. **Scroll + flash** — после добавления слова auto-scroll к новой карточке + flash-подсветка.

## 1. Toolbar

### Текущее состояние

Два уровня:
- **Header** (на всю ширину): `← Back` | Progress bar (Marked: X/Y, To learn: Z) | `Export →`
- **Panel header** (внутри панели кандидатов): `CANDIDATES (N)` + Sort toggle (By relevance | Chronologically) | Generate Meanings / Cancel / Retry | Generate Media / Cancel / Retry

Проблемы: визуальный шум, гигантские лейблы сортировки, бесполезный лейбл «Candidates», count дублирует progress bar, нет места для новых кнопок.

### Новый дизайн

Один ряд, без panel headers:

```
← | 12/47 [===--] learn: 8 | [A↓ T↓] | ···spacer··· | ✨ Meanings | 🎬 Media | + Add | Export →
```

**Убрано:**
- Лейбл «Candidates» — очевидно из контекста
- `(N)` в заголовке — есть в progress bar
- «By relevance / Chronologically» → микро-toggle `A↓` (relevance) / `T↓` (chronological)
- «Source text» label в правой панели — очевидно из содержимого

**Элементы слева направо:**
1. `←` — навигация назад (иконка, без текста «Back»)
2. Progress: `12 / 47 [===--] learn: 8` — компактный inline, прогресс-бар 80px
3. Sort toggle: `[A↓ | T↓]` — микро-переключатель, active = accent background
4. Spacer
5. `✨ Meanings` — генерация meanings
6. `🎬 Media` — генерация media (только для video-источников)
7. `+ Add` — accent-кнопка добавления слова
8. `Export →` — экспорт в Anki

**Состояния Generate-кнопок:**
- **Idle:** ghost-кнопка с иконкой + label
- **Running:** спиннер + count + ✕ cancel. Пример: `⟳ Meanings (14) ✕`
- **Failed:** `↻ Retry (2)` — красный accent

### Компоненты для удаления

- Заголовок `CANDIDATES (N)` внутри панели кандидатов
- Заголовок `Source text` в правой панели
- Отдельный `<header>` элемент с Back/Progress/Export (заменяется единым тулбаром)

## 2. TextSelectionPopover

Один компонент заменяет `SetContextPopover` и `SelectionPopover`.

### Props

```typescript
interface TextSelectionPopoverProps {
  mode: 'edit' | 'add'
  selectedText: string
  position: { x: number; y: number }
  onCancel: () => void

  // Edit mode
  lemma?: string
  pos?: string
  originalFragment?: string       // для diff
  onSetBoundary?: (phrase: string) => void

  // Add mode
  onAddWord?: (target: string, context: string) => void
}
```

### Edit mode

Содержимое поповера:
1. **Header:** лемма + POS слева, мелкий лейбл «EDIT BOUNDARY» справа
2. **Diff-превью:** текст новой фразы с подсветкой изменений:
   - Убранный текст — ~~зачёркнут~~, фон `rgba(red, 0.15)`, красный текст
   - Добавленный текст — фон `rgba(green, 0.15)`, зелёный текст
   - Неизменная часть — нормальный стиль
3. **Подпись:** `Was: «{originalFragment}»` — мелким, для контекста
4. **Кнопки:** Cancel | Set boundary (accent)

Diff вычисляется на фронте. Алгоритм: оба фрагмента содержат target word (lemma), поэтому разбиваем каждый фрагмент на три части — текст до target, target, текст после target. Сравниваем prefix и suffix старого и нового фрагментов. Части, которые есть в старом, но нет в новом — красные (removed). Части в новом, но не в старом — зелёные (added). Target и совпадающие части — нормальный стиль. Это простое сравнение, не full diff library.

### Add mode

Содержимое поповера:
1. **Header:** мелкий лейбл «TAP WORDS TO SELECT TARGET»
2. **Текст фразы:** выглядит как обычный текст (не пилюли, не кнопки). Слова кликабельны. При наведении — лёгкий hover. При клике на слово:
   - Выбранное слово получает: accent background `rgba(purple, 0.2)` + `border-bottom: 2px solid accent`
   - Остальные слова приглушаются до `opacity: 0.5`
   - Можно выбрать несколько слов (для фразовых глаголов: «put» + «off»)
   - Повторный клик снимает выделение
3. **Превью target:** `Target: {selected words joined}` — появляется после первого клика
4. **Кнопки:** Cancel | Add word (accent). «Add word» disabled пока ни одно слово не выбрано

### Общее поведение

- **Позиционирование:** привязан к выделению текста, появляется снизу
- **Dismiss:** клик вне поповера / Escape / Cancel
- **Анимация:** fade-in при появлении

### Компоненты для удаления

- `SetContextPopover.tsx` — полностью заменяется
- `SelectionPopover.tsx` — полностью заменяется

## 3. Flows

### Flow «Edit boundary»

1. Пользователь кликает **✏ (карандаш)** на карточке кандидата
2. В тулбаре появляется inline-баннер: **«Selecting boundary for: {lemma}»** + ✕
3. Левая панель **приглушается**, правая получает **accent-border + inner glow** — аналогично Add mode
4. Пользователь выделяет новый текст в правой панели
5. Появляется `TextSelectionPopover` в режиме `edit` с diff-превью
6. Пользователь кликает «Set boundary»
7. PATCH `/candidates/{id}/context-fragment` → обновление карточки
8. Режим Edit завершается: баннер исчезает, opacity и border сбрасываются

### Flow «+ Add word» — шаги

1. Пользователь кликает **«+ Add»** в тулбаре
2. Кнопка «+ Add» заменяется на inline-баннер: **«Select text in source →»** + ✕
3. Левая панель (карточки) **приглушается** (`opacity ~0.4`) — фокус на текст
4. Правая панель получает **accent-border** (`1.5px solid rgba(accent, 0.3)`) + **inner glow** (`box-shadow: inset 0 0 20px rgba(accent, 0.05)`) — визуальное указание «действуй здесь»
5. Пользователь выделяет текст в правой панели
6. Появляется `TextSelectionPopover` в режиме `add`
7. Пользователь выбирает target-слова, кликает «Add word»
8. POST `/sources/{id}/candidates/manual` → refetch кандидатов
9. Режим Add завершается: баннер исчезает, кнопка «+ Add» возвращается, opacity и border сбрасываются
10. **Scroll + flash** к новой карточке (см. секцию 4)

### Отмена (оба flow)

- Клик ✕ в баннере или Escape — выход из режима (Add/Edit), всё возвращается к нормальному состоянию
- Cancel в поповере — закрывает поповер, но остаётся в режиме (можно выделить другой текст)

## 4. Scroll + flash после добавления

После успешного POST и refetch:

1. Бэкенд возвращает `StoredCandidateDTO` с `id`
2. После refetch — находим карточку с этим `id` в DOM (через `ref` или `querySelector`)
3. `scrollIntoView({ behavior: 'smooth', block: 'center' })` — карточка плавно появляется по центру панели кандидатов
4. CSS-анимация на карточке: `@keyframes card-flash` — accent glow на border/box-shadow, затухает за 2 секунды

```css
@keyframes card-flash {
  0%   { box-shadow: 0 0 0 2px rgba(accent, 0.6), 0 0 16px rgba(accent, 0.2); }
  100% { box-shadow: 0 0 0 0px rgba(accent, 0), 0 0 0px rgba(accent, 0); }
}
```

Применяется через временный CSS-класс, который снимается по `animationend`.

## 5. Файловые изменения

### Новые файлы
- `frontends/web/src/components/TextSelectionPopover.tsx` — единый поповер

### Изменяемые файлы
- `frontends/web/src/pages/ReviewPage.tsx` — переработка тулбара, flow Add word, scroll+flash, state management
- `frontends/web/src/components/TextAnnotator.tsx` — убрать логику вызова `SelectionPopover`, адаптировать под новый поповер
- `frontends/web/src/components/CandidateCardV2.tsx` — убрать reference на `SetContextPopover` если есть

### Удаляемые файлы
- `frontends/web/src/components/SetContextPopover.tsx`
- `frontends/web/src/components/SelectionPopover.tsx`

### Бэкенд

Без изменений. API endpoints остаются:
- `PATCH /candidates/{id}/context-fragment` — для edit boundary
- `POST /sources/{id}/candidates/manual` — для add word
