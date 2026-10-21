import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { SourceDocument, StoredCandidate } from '@/api/types'
import { Icon } from '@/ui'
import { findMark } from './findMark'
import { SourceText, type SelectedText, type SelectionPoint } from './SourceText'
import css from './review.module.css'

interface SourceTextsProps {
  /** Тексты источников набора в порядке набора. */
  documents: SourceDocument[]
  /** Разобрана ли карточка — из ответов ревью, поверх отметок самого текста. */
  done: ReadonlyMap<number, boolean>
  /** Карточка, чья фраза подсвечена: текущая или та, чью границу правят. */
  focused: StoredCandidate | null
  /** Источник фразы, чью границу правят: выделение принимает только его текст. */
  editingSourceId: number | null
  onWordClick: (candidateId: number) => void
  onTextSelected: (selected: SelectedText, point: SelectionPoint) => void
}

/** Тексты всех источников набора подряд, у каждого заголовок; прокручиваются одной колонкой.
 * Когда текстов больше одного, каждый сворачивается до заголовка. */
export function SourceTexts({ documents, done, focused, editingSourceId, onWordClick, onTextSelected }: SourceTextsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const focusId = focused?.phrase_id ?? null
  const [folded, setFolded] = useState<ReadonlySet<number>>(new Set())
  const foldable = documents.length > 1
  const toggle = (sourceId: number) => setFolded(prev => {
    const next = new Set(prev)
    if (!next.delete(sourceId)) next.add(sourceId)
    return next
  })

  // Держим слово текущей фразы в видимой части колонки; ищем его в тексте источника карточки.
  useEffect(() => {
    const container = containerRef.current
    if (!container || focusId === null || !focused) return
    const text = container.querySelector(`[data-source-id="${focused.source.id}"]`) ?? container
    const mark = findMark(text, focusId, focused.source_phrase.text)
    if (!mark) return
    // Останавливаемся на границе строки, чтобы верхняя видимая строка была целой.
    const lineHeight = parseFloat(getComputedStyle(container).lineHeight)
    const top = Math.round((mark.offsetTop - container.clientHeight / 2) / lineHeight) * lineHeight
    container.scrollTo({ top, behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- прокручиваем при смене фразы, а не при каждом обновлении списка
  }, [focusId])

  return (
    <div ref={containerRef} className={css.source}>
      {documents.map(document => {
        const selectable = editingSourceId === null || editingSourceId === document.source_id
        const open = !folded.has(document.source_id)
        return (
          <section key={document.source_id} className={css.sourceDocument} data-source-id={document.source_id} data-selectable={selectable || undefined}>
            <h3 className={css.sourceTitle}>
              {foldable
                ? <button type="button" className={css.sourceFold} aria-expanded={open} onClick={() => toggle(document.source_id)}>
                    <span className={css.sourceChevron}><Icon as={open ? ChevronDown : ChevronRight} size="s" /></span>
                    <span className={css.sourceFoldTitle}>{document.title}</span>
                    {!open && <span className={css.sourceEllipsis} aria-hidden>…</span>}
                  </button>
                : document.title}
            </h3>
            {open && (
              <SourceText
                document={document}
                done={done}
                focused={focused}
                onWordClick={onWordClick}
                onTextSelected={selectable ? onTextSelected : undefined}
              />
            )}
          </section>
        )
      })}
    </div>
  )
}
