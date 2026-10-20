import { useEffect, useRef } from 'react'
import type { SourceDocument, StoredCandidate } from '@/api/types'
import { findMark } from './findMark'
import { SourceText, type SelectedText, type SelectionPoint } from './SourceText'
import css from './review.module.css'

interface SourceTextsProps {
  /** Тексты источников набора в порядке набора. */
  documents: SourceDocument[]
  candidates: StoredCandidate[]
  /** Кандидат, чья фраза подсвечена: текущая фраза или фраза в режиме правки. */
  focusId: number | null
  /** Источник фразы, чью границу правят: выделение принимает только его текст. */
  editingSourceId: number | null
  onWordClick: (candidateId: number) => void
  onTextSelected: (selected: SelectedText, point: SelectionPoint) => void
}

/** Тексты всех источников набора подряд, у каждого заголовок; прокручиваются одной колонкой. */
export function SourceTexts({ documents, candidates, focusId, editingSourceId, onWordClick, onTextSelected }: SourceTextsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const focused = candidates.find(c => c.phrase_id === focusId)

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
        return (
          <section key={document.source_id} className={css.sourceDocument} data-source-id={document.source_id} data-selectable={selectable || undefined}>
            <h3 className={css.sourceTitle}>{document.title}</h3>
            <SourceText
              document={document}
              candidates={candidates}
              focusId={focusId}
              onWordClick={onWordClick}
              onTextSelected={selectable ? onTextSelected : undefined}
            />
          </section>
        )
      })}
    </div>
  )
}
