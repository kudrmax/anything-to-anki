import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import '@/styles/base.css'
import { api } from '@/api/client'
import { useApplyTheme } from '@/lib/theme'
import { quickAddPanel } from '@/lib/nativeHost'
import { Button, Toast, useToast } from '@/ui'
import phrase from '@/ui/phrase.module.css'
import { normalizePhrase, snapToWords, type Span } from './targetSpan'
import css from './QuickAdd.module.css'

export const QUICK_ADD_PATH = '/quick-add'
const TEXT_PARAM = 'text'
const SAVED_MESSAGE = 'Saved to Saved phrases'
/** Пауза, чтобы успеть увидеть подтверждение, прежде чем панель закроется. */
const CLOSE_AFTER_SAVE_MS = 900

/** Сколько символов фразы стоит до точки (node, offset) внутри контейнера. */
function offsetIn(container: Node, node: Node, offset: number): number {
  const range = document.createRange()
  range.selectNodeContents(container)
  range.setEnd(node, offset)
  return range.toString().length
}

export function QuickAddScreen() {
  useApplyTheme()
  const [params] = useSearchParams()
  const text = normalizePhrase(params.get(TEXT_PARAM) ?? '')
  const [target, setTarget] = useState<Span | null>(null)
  const [toast, showToast] = useToast()
  const [saving, setSaving] = useState(false)
  const phraseRef = useRef<HTMLParagraphElement>(null)
  const panel = quickAddPanel()

  const pickTarget = () => {
    const container = phraseRef.current
    const selection = window.getSelection()
    if (!container || !selection || selection.isCollapsed || !selection.rangeCount) return
    const range = selection.getRangeAt(0)
    if (!container.contains(range.commonAncestorContainer)) return
    const span = snapToWords(
      text,
      offsetIn(container, range.startContainer, range.startOffset),
      offsetIn(container, range.endContainer, range.endOffset),
    )
    selection.removeAllRanges()
    if (span) setTarget(span)
  }

  const save = useCallback(async () => {
    if (!target || saving) return
    setSaving(true)
    try {
      await api.addSavedPhrase(text, text.slice(target.start, target.end))
      showToast(SAVED_MESSAGE)
      setTarget(null)
      if (panel) window.setTimeout(() => panel.close(), CLOSE_AFTER_SAVE_MS)
    } catch (e) {
      showToast(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }, [panel, saving, showToast, target, text])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') panel?.close()
      if (e.key === 'Enter') void save()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [panel, save])

  return (
    <div className={css.screen}>
      <div className={css.label}>Add to AnythingToAnki</div>
      {text ? (
        <p ref={phraseRef} className={css.phrase} onMouseUp={pickTarget}>
          {target ? (
            <>
              {text.slice(0, target.start)}
              <span className={`${phrase.target} ${phrase.targetCurrent}`}>{text.slice(target.start, target.end)}</span>
              {text.slice(target.end)}
            </>
          ) : text}
        </p>
      ) : (
        <p className={css.empty}>No text came with the request.</p>
      )}
      <div className={css.hint}>
        {target ? 'Target picked. Select again to change it.' : 'Select the word, phrasal verb or collocation to learn.'}
      </div>
      <div className={css.actions}>
        {panel && <Button variant="link" onClick={() => panel.close()} kbd="esc">Cancel</Button>}
        <Button variant="fill" disabled={!target} busy={saving} onClick={() => void save()} kbd="↵">Save</Button>
      </div>
      <Toast message={toast} />
    </div>
  )
}
