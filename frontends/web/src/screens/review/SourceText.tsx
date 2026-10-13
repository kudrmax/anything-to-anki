import { Fragment, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import type { DocumentBlock, DocumentSelection, SourceDocument, StoredCandidate } from '@/api/types'
import { codePointOffset, lineSegments, type LineMark } from '@/lib/text/documentSegments'
import { findMark } from './findMark'
import css from './review.module.css'

export interface SelectionPoint {
  x: number
  top: number
  bottom: number
}

export interface SelectedText {
  /** Выделенный текст — чтобы показать его и выбрать в нём слова. */
  text: string
  selection: DocumentSelection
}

interface SourceTextProps {
  document: SourceDocument
  candidates: StoredCandidate[]
  /** Кандидат, чья фраза подсвечена: текущая фраза или фраза в режиме правки. */
  focusId: number | null
  onWordClick: (candidateId: number) => void
  onTextSelected: (selected: SelectedText, point: SelectionPoint) => void
}

const TOUCH_QUERY = '(hover: none)'
const TOUCH_SELECTION_SETTLE_MS = 600
const SEGMENT_SELECTOR = '[data-line]'

interface DocumentPoint {
  block: number
  line: number
  char: number
}

/** Место в документе, где проходит граница выделения: кусок строки и смещение в нём. */
function documentPoint(node: Node, offset: number, isEnd: boolean): DocumentPoint | null {
  let target: Node | null = node
  let within = offset
  if (node.nodeType !== Node.TEXT_NODE) {
    const children = node.childNodes
    const child = isEnd ? children[offset - 1] : children[offset]
    if (!child) return null
    const texts = textNodes(child)
    target = isEnd ? texts[texts.length - 1] ?? null : texts[0] ?? null
    within = isEnd && target ? (target.textContent ?? '').length : 0
  }
  const segment = target?.parentElement?.closest<HTMLElement>(SEGMENT_SELECTOR)
  if (!target || !segment) return null
  return {
    block: Number(segment.dataset.block),
    line: Number(segment.dataset.line),
    char: Number(segment.dataset.start) + codePointOffset(target.textContent ?? '', within),
  }
}

function textNodes(node: Node): Node[] {
  if (node.nodeType === Node.TEXT_NODE) return [node]
  return Array.from(node.childNodes).flatMap(textNodes)
}

const lineSeparator = (block: DocumentBlock): string => (block.mode === 'lines' ? '\n' : ' ')
const BULLET = '•'

/** Маркер каждого пункта списка: точка или номер среди соседних пунктов той же глубины. */
function listMarkers(blocks: readonly DocumentBlock[]): (string | null)[] {
  const counters: number[] = []
  return blocks.map(block => {
    if (block.type !== 'list_item') {
      counters.length = 0
      return null
    }
    const depth = block.depth ?? 0
    counters.length = depth + 1
    counters[depth] = (counters[depth] ?? 0) + 1
    return block.ordered ? `${counters[depth]}.` : BULLET
  })
}

export function SourceText({ document, candidates, focusId, onWordClick, onTextSelected }: SourceTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const marks = useMemo<LineMark[]>(
    () => document.highlights.map(h => ({ candidateId: h.candidate_id, position: h.position })),
    [document],
  )
  const markers = useMemo(() => listMarkers(document.blocks), [document])
  const ratedIds = useMemo(() => new Set(candidates.filter(c => c.status !== 'pending').map(c => c.id)), [candidates])
  const focused = candidates.find(c => c.id === focusId)
  const fragment = focused && !focused.has_custom_context_fragment ? focused.phrase_position : null

  // Держим слово текущей фразы в видимой части колонки.
  useEffect(() => {
    const container = containerRef.current
    const mark = container && focusId !== null ? findMark(container, focusId, focused?.context_fragment ?? '') : null
    if (!container || !mark) return
    // Останавливаемся на границе строки, чтобы верхняя видимая строка была целой.
    const lineHeight = parseFloat(getComputedStyle(container).lineHeight)
    const top = Math.round((mark.offsetTop - container.clientHeight / 2) / lineHeight) * lineHeight
    container.scrollTo({ top, behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- прокручиваем при смене фразы, а не при каждом обновлении списка
  }, [focusId])

  const reportSelection = () => {
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || !selection.rangeCount) return
    if (!containerRef.current?.contains(selection.anchorNode)) return
    const text = selection.toString().trim()
    if (!text) return
    const range = selection.getRangeAt(0)
    const start = documentPoint(range.startContainer, range.startOffset, false)
    const end = documentPoint(range.endContainer, range.endOffset, true)
    if (!start || !end) return
    const rect = range.getBoundingClientRect()
    onTextSelected(
      {
        text,
        selection: {
          start_block: start.block, start_line: start.line, start_char: start.char,
          end_block: end.block, end_line: end.line, end_char: end.char,
        },
      },
      { x: rect.left, top: rect.top, bottom: rect.bottom },
    )
  }

  // На касании mouseup после выделения не приходит: ждём, пока пользователь перестанет двигать границы.
  useEffect(() => {
    if (!window.matchMedia(TOUCH_QUERY).matches) return
    let timer: number | undefined
    const onSelectionChange = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(reportSelection, TOUCH_SELECTION_SETTLE_MS)
    }
    window.document.addEventListener('selectionchange', onSelectionChange)
    return () => {
      window.clearTimeout(timer)
      window.document.removeEventListener('selectionchange', onSelectionChange)
    }
  })

  const renderLine = (block: DocumentBlock, blockIndex: number, lineIndex: number) =>
    lineSegments(block.lines[lineIndex].text, blockIndex, lineIndex, marks, fragment).map(segment => {
      const data = { 'data-block': blockIndex, 'data-line': lineIndex, 'data-start': segment.start }
      if (segment.markId === null) {
        return <span key={segment.start} {...data} className={segment.inFragment ? css.fragment : undefined}>{segment.text}</span>
      }
      const id = segment.markId
      const state = id === focusId ? css.markCurrent : ratedIds.has(id) ? css.markRated : css.markPending
      const classes = [css.mark, state, segment.inFragment && css.fragment].filter(Boolean).join(' ')
      return (
        <mark key={segment.start} {...data} data-mark-id={id} className={classes} onClick={() => onWordClick(id)}>
          {segment.text}
        </mark>
      )
    })

  const renderBlock = (block: DocumentBlock, blockIndex: number) => {
    const lines = block.lines.map((_, lineIndex) => (
      <Fragment key={lineIndex}>
        {lineIndex > 0 && lineSeparator(block)}
        {renderLine(block, blockIndex, lineIndex)}
      </Fragment>
    ))
    if (block.type === 'heading') return <div key={blockIndex} className={css.heading}>{lines}</div>
    if (block.type === 'list_item') {
      return (
        <div key={blockIndex} className={css.listItem} style={{ '--depth': block.depth ?? 0 } as CSSProperties}>
          <span className={css.listMarker} aria-hidden>{markers[blockIndex]}</span>
          <span>{lines}</span>
        </div>
      )
    }
    return <div key={blockIndex} className={css.block}>{lines}</div>
  }

  return (
    <div ref={containerRef} className={css.source} onMouseUp={reportSelection}>
      {document.blocks.map(renderBlock)}
    </div>
  )
}
