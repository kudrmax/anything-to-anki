import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import '@/styles/base.css'
import { api } from '@/api/client'
import { useApplyTheme } from '@/lib/theme'
import { quickAddPanel } from '@/lib/nativeHost'
import { Button, Toast, useToast } from '@/ui'
import phrase from '@/ui/phrase.module.css'
import { normalizePhrase, pickSpan, segments, snapToWords, targetText, type Span } from './targetSpan'
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
  const [target, setTarget] = useState<Span[]>([])
  const [toast, showToast] = useToast()
  const [saving, setSaving] = useState(false)
  const phraseRef = useRef<HTMLParagraphElement>(null)
  const panel = quickAddPanel()

  const pickTarget = (e: MouseEvent) => {
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
    if (span) setTarget(prev => pickSpan(prev, span, e.metaKey))
  }

  const save = useCallback(async () => {
    if (!target.length || saving) return
    setSaving(true)
    try {
      await api.addSavedPhrase(text, targetText(text, target))
      showToast(SAVED_MESSAGE)
      setTarget([])
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
          {segments(text, target).map((segment, i) => (segment.picked
            ? <span key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{segment.text}</span>
            : segment.text))}
        </p>
      ) : (
        <p className={css.empty}>No text came with the request.</p>
      )}
      <div className={css.hint}>
        {target.length
          ? `Target: ${targetText(text, target)}. Select again to change it, hold ⌘ to add or remove words.`
          : 'Select the word, phrasal verb or collocation to learn. Hold ⌘ to pick separated words, like give … up.'}
      </div>
      <div className={css.actions}>
        {panel && <Button variant="link" onClick={() => panel.close()} kbd="esc">Cancel</Button>}
        <Button variant="fill" disabled={!target.length} busy={saving} onClick={() => void save()} kbd="↵">Save</Button>
      </div>
      <Toast message={toast} />
    </div>
  )
}
