import { useMemo, useRef } from 'react'
import { useEffect } from 'react'
import type { StoredCandidate } from '@/api/types'
import { buildSegments, fragmentBounds } from '@/lib/text/segments'
import css from './review.module.css'

export interface SelectionPoint {
  x: number
  top: number
  bottom: number
}

interface SourceTextProps {
  text: string
  candidates: StoredCandidate[]
  /** Кандидат, чей фрагмент подсвечен: текущая фраза или фраза в режиме правки. */
  focusId: number | null
  onWordClick: (candidateId: number) => void
  onTextSelected: (phrase: string, point: SelectionPoint) => void
}

const SINGLE_BREAK = /(?<!\n)\n(?!\n)/g
/** Одиночный перенос строки — часть того же абзаца, пустая строка — новый абзац. */
const flow = (text: string): string => text.replace(SINGLE_BREAK, ' ')

export function SourceText({ text, candidates, focusId, onWordClick, onTextSelected }: SourceTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const segments = useMemo(() => buildSegments(text, candidates), [text, candidates])
  const ratedIds = useMemo(() => new Set(candidates.filter(c => c.status !== 'pending').map(c => c.id)), [candidates])
  const bounds = fragmentBounds(text, candidates.find(c => c.id === focusId))

  // Держим слово текущей фразы в видимой части колонки.
  useEffect(() => {
    const container = containerRef.current
    const mark = container?.querySelector<HTMLElement>(`[data-mark-id="${focusId}"]`)
    if (!container || !mark) return
    container.scrollTo({ top: mark.offsetTop - container.clientHeight / 2, behavior: 'smooth' })
  }, [focusId])

  const onMouseUp = () => {
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || !selection.rangeCount) return
    const phrase = selection.toString().trim()
    if (!phrase) return
    const rect = selection.getRangeAt(0).getBoundingClientRect()
    onTextSelected(phrase, { x: rect.left, top: rect.top, bottom: rect.bottom })
  }

  const inFragment = (start: number, end: number) => bounds !== null && start < bounds.end && end > bounds.start

  return (
    <div ref={containerRef} className={css.source} onMouseUp={onMouseUp}>
      {segments.map((segment, i) => {
        const end = segment.start + segment.content.length
        if (segment.type === 'text') {
          if (!bounds || !inFragment(segment.start, end)) return <span key={i}>{flow(segment.content)}</span>
          const from = Math.max(segment.start, bounds.start) - segment.start
          const to = Math.min(end, bounds.end) - segment.start
          return (
            <span key={i}>
              {flow(segment.content.slice(0, from))}
              <span className={css.fragment}>{flow(segment.content.slice(from, to))}</span>
              {flow(segment.content.slice(to))}
            </span>
          )
        }
        const state = segment.candidateId === focusId ? css.markCurrent : ratedIds.has(segment.candidateId) ? css.markRated : css.markPending
        return (
          <mark key={i} data-mark-id={segment.candidateId} className={`${css.mark} ${state}`} onClick={() => onWordClick(segment.candidateId)}>
            {segment.content.replace(/\s+/g, ' ')}
          </mark>
        )
      })}
    </div>
  )
}
