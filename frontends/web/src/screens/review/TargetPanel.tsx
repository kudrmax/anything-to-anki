import { useEffect } from 'react'
import { clozePanelKey } from '@/lib/clozeKeys'
import { Button } from '@/ui'
import type { TargetEditor } from './useTargetEditor'
import css from './review.module.css'

/**
 * Панель выбора таргета под фразой. Enter меняет таргет, Esc отменяет — те же клавиши, что у разметки cloze.
 * Карточка с новым таргетом — новая карточка: meaning, аудио и cloze делаются заново.
 */
export function TargetPanel({ editor }: { editor: TargetEditor }) {
  const { cancel, save } = editor

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = clozePanelKey(e)
      if (!key) return
      e.preventDefault()
      if (key === 'cancel') cancel()
      else void save()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [cancel, save])

  return (
    <div className={css.clozePanel}>
      <div className={css.clozeActions}>
        <p className={css.clozeTip}>Click words to pick the target</p>
        <Button variant="link" kbd="Esc" onClick={cancel}>Cancel</Button>
        <Button variant="fill" kbd="↵" busy={editor.saving} disabled={!editor.canSave} onClick={() => void save()}>Change target</Button>
      </div>
    </div>
  )
}
