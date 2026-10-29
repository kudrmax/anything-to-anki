import { Fragment, memo, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import type { DocumentBlock, DocumentPosition, DocumentSelection, Highlight, StoredCandidate, TextChunk } from '@/api/types'
import { codePointOffset, lineSegments, type LineMark } from '@/lib/text/documentSegments'
import type { DoneMark } from './reviewState'
import { chunkHighlights, isDoneIn, isTextGap, type TextGap, type TextItem, type TextState } from './textState'
import { TEXT_PX_PER_CHAR } from './textPlaceholders'
import css from './review.module.css'

export interface SelectionPoint {
  x: number
  top: number
  bottom: number
}

export interface SelectedText {
  /** Источник, в тексте которого выделили: новая карточка добавляется в него. */
  sourceId: number
  /** Выделенный текст — чтобы показать его и выбрать в нём слова. */
  text: string
  selection: DocumentSelection
}


interface SourceTextProps {
  sourceId: number
  /** Загруженные куски и незагруженные участки между ними, по порядку. */
  items: readonly TextItem[]
  text: TextState
  /** «Разобрана» из ответов ревью: сравнивается с подсветкой куска по ревизии. */
  done: ReadonlyMap<number, DoneMark>
  /** Карточка, чья фраза подсвечена: текущая или та, чью границу правят. */
  focused: StoredCandidate | null
  onWordClick: (candidateId: number) => void
  /** Нет — выделение в этом тексте ничего не делает (правится граница фразы другого источника). */
  onTextSelected?: (selected: SelectedText, point: SelectionPoint) => void
}

const TOUCH_QUERY = '(hover: none)'
const TOUCH_SELECTION_SETTLE_MS = 600
const SEGMENT_SELECTOR = '[data-line]'
const BULLET = '•'

interface DocumentPoint {
  block: number
  line: number
  char: number
}

/** Место в документе, где проходит граница выделения. Край на переносе строки, между блоками или на маркере
 *  списка не лежит ни в одном куске строки: он сдвигается к ближайшему куску внутри выделения. */
function documentPoint(range: Range, container: HTMLElement, isEnd: boolean): DocumentPoint | null {
  const node = isEnd ? range.endContainer : range.startContainer
  const segment = node.nodeType === Node.TEXT_NODE ? node.parentElement?.closest<HTMLElement>(SEGMENT_SELECTOR) : null
  if (segment) return pointIn(segment, isEnd ? range.endOffset : range.startOffset)
  const touched = [...container.querySelectorAll<HTMLElement>(SEGMENT_SELECTOR)].filter(s => range.intersectsNode(s))
  const nearest = isEnd ? touched.at(-1) : touched[0]
  if (!nearest) return null
  return pointIn(nearest, isEnd ? (nearest.textContent ?? '').length : 0)
}

function pointIn(segment: HTMLElement, offset: number): DocumentPoint {
  return {
    block: Number(segment.dataset.block),
    line: Number(segment.dataset.line),
    char: Number(segment.dataset.start) + codePointOffset(segment.textContent ?? '', offset),
  }
}

const lineSeparator = (block: DocumentBlock): string => (block.mode === 'lines' ? '\n' : ' ')

const listMarker = (block: DocumentBlock): string =>
  (block.ordered && block.number !== null ? `${block.number}.` : BULLET)

interface ChunkViewProps {
  chunk: TextChunk
  highlights: readonly Highlight[]
  /** Подсвеченная фраза, если она в этом куске. */
  focusId: number | null
  fragment: DocumentPosition | null
  /** Разобранные карточки куска одной строкой: кусок перерисовывается, только когда они меняются. */
  doneKey: string
  onWordClick: (candidateId: number) => void
}

/** Блоки одного куска с абсолютными номерами. */
const ChunkView = memo(function ChunkView({ chunk, highlights, focusId, fragment, doneKey, onWordClick }: ChunkViewProps) {
  const marksByBlock = useMemo(() => {
    const byBlock = new Map<number, LineMark[]>()
    for (const h of highlights) {
      const list = byBlock.get(h.position.block) ?? []
      list.push({ candidateId: h.phrase_id, position: h.position })
      byBlock.set(h.position.block, list)
    }
    return byBlock
  }, [highlights])
  const doneIds = useMemo(() => new Set(doneKey.split(',').filter(Boolean).map(Number)), [doneKey])

  const renderLine = (block: DocumentBlock, blockIndex: number, lineIndex: number) =>
    lineSegments(block.lines[lineIndex].text, blockIndex, lineIndex, marksByBlock.get(blockIndex) ?? [], fragment).map(segment => {
      const data = { 'data-block': blockIndex, 'data-line': lineIndex, 'data-start': segment.start }
      if (segment.markId === null) {
        return <span key={segment.start} {...data} className={segment.inFragment ? css.fragment : undefined}>{segment.text}</span>
      }
      const id = segment.markId
      const state = id === focusId ? css.markCurrent : doneIds.has(id) ? css.markRated : css.markPending
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
    const data = { 'data-text-block': blockIndex }
    if (block.type === 'heading') return <div key={blockIndex} {...data} className={css.heading}>{lines}</div>
    if (block.type === 'list_item') {
      return (
        <div key={blockIndex} {...data} className={css.listItem} style={{ '--depth': block.depth ?? 0 } as CSSProperties}>
          <span className={css.listMarker} aria-hidden>{listMarker(block)}</span>
          <span>{lines}</span>
        </div>
      )
    }
    return <div key={blockIndex} {...data} className={css.block}>{lines}</div>
  }

  return <>{chunk.blocks.map((block, i) => renderBlock(block, chunk.first_block + i))}</>
})

/** Незагруженные блоки [start, end): заглушка высотой по их размеру. */
function GapView({ sourceId, gap }: { sourceId: number; gap: TextGap }) {
  return (
    <div
      className={css.placeholder}
      data-text-gap
      data-source-id={sourceId}
      data-gap-start={gap.start}
      data-gap-end={gap.end ?? undefined}
      data-gap-offset={gap.start_offset}
      style={{ '--placeholder-h': `${Math.round(gap.chars * TEXT_PX_PER_CHAR)}px` } as CSSProperties}
      aria-hidden
    />
  )
}

/** Текст одного источника: загруженные куски и заглушки между ними — одно поле выделения. */
export function SourceText({ sourceId, items, text, done, focused, onWordClick, onTextSelected }: SourceTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const focusId = focused?.phrase_id ?? null
  // Фрагмент фразы подсвечивается только в тексте её источника: позиции у каждого документа свои.
  const fragment = focused?.source.id === sourceId ? focused.phrase_position : null

  const reportSelection = () => {
    const selection = window.getSelection()
    if (!onTextSelected || !selection || selection.isCollapsed || !selection.rangeCount) return
    // Выделение, ушедшее в текст другого источника, не задаёт место ни в одном документе.
    const container = containerRef.current
    if (!container?.contains(selection.anchorNode) || !container.contains(selection.focusNode)) return
    const selected = selection.toString().trim()
    if (!selected) return
    const range = selection.getRangeAt(0)
    const start = documentPoint(range, container, false)
    const end = documentPoint(range, container, true)
    if (!start || !end) return
    const rect = range.getBoundingClientRect()
    onTextSelected(
      {
        sourceId,
        text: selected,
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

  // Выделение тянут и за край колонки: кнопку отпускают где угодно, но начинали в этом тексте.
  const selecting = useRef(false)
  useEffect(() => {
    const onMouseUp = () => {
      if (!selecting.current) return
      selecting.current = false
      reportSelection()
    }
    window.document.addEventListener('mouseup', onMouseUp)
    return () => window.document.removeEventListener('mouseup', onMouseUp)
  })

  const inChunk = (chunk: TextChunk, position: DocumentPosition | null): boolean =>
    position !== null && chunk.first_block <= position.block && position.block < chunk.end_block

  return (
    <div ref={containerRef} onMouseDown={() => { selecting.current = true }}>
      {items.map(item => {
        if (isTextGap(item)) return <GapView key={`gap-${item.gap.start}`} sourceId={sourceId} gap={item.gap} />
        const { chunk } = item
        const highlights = chunkHighlights(text, chunk)
        const doneKey = highlights.filter(h => isDoneIn(text, done, h.phrase_id)).map(h => h.phrase_id).join(',')
        const holdsFocus = highlights.some(h => h.phrase_id === focusId)
        return (
          <ChunkView
            key={chunk.first_block}
            chunk={chunk}
            highlights={highlights}
            focusId={holdsFocus ? focusId : null}
            fragment={inChunk(chunk, fragment) ? fragment : null}
            doneKey={doneKey}
            onWordClick={onWordClick}
          />
        )
      })}
    </div>
  )
}
