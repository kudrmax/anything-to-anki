import { useMemo, useRef } from 'react'
import { useEffect } from 'react'
import type { StoredCandidate } from '@/api/types'
import { buildSegments, fragmentBounds } from '@/lib/text/segments'
import { findMark } from './findMark'
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
    const fragment = candidates.find(c => c.id === focusId)?.context_fragment ?? ''
    const mark = container && focusId !== null ? findMark(container, focusId, fragment) : null
    if (!container || !mark) return
    // Останавливаемся на границе строки, чтобы верхняя видимая строка была целой.
    const lineHeight = parseFloat(getComputedStyle(container).lineHeight)
    const top = Math.round((mark.offsetTop - container.clientHeight / 2) / lineHeight) * lineHeight
    container.scrollTo({ top, behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- прокручиваем при смене фразы, а не при каждом обновлении списка
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
        const classes = [css.mark, state, inFragment(segment.start, end) && css.fragment].filter(Boolean).join(' ')
        return (
          <mark key={i} data-mark-id={segment.candidateId} className={classes} onClick={() => onWordClick(segment.candidateId)}>
            {segment.content.replace(/\s+/g, ' ')}
          </mark>
        )
      })}
    </div>
  )
}
