import { useEffect } from 'react'
import type { ClozePreview } from '@/api/types'
import { CLOZE_GAP, CLOZE_HINT_OPTIONS } from '@/lib/clozeHints'
import { OVERLAY } from '@/lib/hotkeys'
import { Button, Field, Segmented, Text } from '@/ui'
import type { ClozeEditor } from './useClozeEditor'
import css from './review.module.css'

function AnkiFront({ preview }: { preview: ClozePreview }) {
  const parts = preview.front.split(CLOZE_GAP)
  return (
    <p className={css.clozeFront}>
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span className={css.clozeBlank}>{CLOZE_GAP}</span>}
          {part}
        </span>
      ))}
      {preview.hint && <span className={css.clozeFrontHint}> ({preview.hint})</span>}
    </p>
  )
}

/**
 * Панель разметки cloze под фразой: подсказка, лицевая сторона в Anki, сохранение.
 * Enter сохраняет (кроме кнопки в фокусе — она нажимается сама), Esc отменяет.
 */
export function ClozePanel({ editor }: { editor: ClozeEditor }) {
  const { draft, preview, error, cancel, save } = editor

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat) return
      if (document.querySelector(OVERLAY)) return
      const target = e.target instanceof Element ? e.target : null
      // Поле правки фразы живёт своими клавишами.
      if (target?.closest('textarea')) return
      if (e.key === 'Escape') {
        e.preventDefault()
        cancel()
      } else if (e.key === 'Enter') {
        // Кнопка в фокусе (слово, подсказка, Cancel, Save) нажимается сама.
        if (target?.closest('button')) return
        e.preventDefault()
        void save()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [cancel, save])

  const hintOptions = CLOZE_HINT_OPTIONS.map(option => ({
    ...option,
    disabled: preview !== null && !preview.available_hints.includes(option.value),
  }))

  return (
    <div className={css.clozePanel}>
      {draft && preview && (
        <div className={css.clozeCols}>
          <div className={css.clozeField}>
            <span className={css.clozeLabel}>Hint</span>
            <Segmented className={css.clozeHints} value={draft.hint_kind} options={hintOptions} onChange={editor.setHintKind} />
            {draft.hint_kind === 'custom' && (
              <Field
                autoFocus
                value={draft.custom_hint ?? ''}
                placeholder="Your hint…"
                aria-label="Your hint"
                onChange={e => editor.setCustomHint(e.target.value)}
              />
            )}
          </div>
          <div className={css.clozeField}>
            <span className={css.clozeLabel}>Anki front</span>
            <AnkiFront preview={preview} />
          </div>
        </div>
      )}
      {error && <Text tone="err" size="s">{error}</Text>}
      <div className={css.clozeActions}>
        <p className={css.clozeTip}>Click words to hide or show them</p>
        <Button variant="link" kbd="Esc" onClick={cancel}>Cancel</Button>
        <Button variant="fill" kbd="↵" busy={editor.saving} disabled={!editor.canSave} onClick={() => void save()}>Save cloze</Button>
      </div>
    </div>
  )
}
