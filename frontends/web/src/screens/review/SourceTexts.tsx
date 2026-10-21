import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { StoredCandidate, TextPlace } from '@/api/types'
import { Icon } from '@/ui'
import { findMark } from './findMark'
import type { DoneMark } from './reviewState'
import { SourceText, type SelectedText, type SelectionPoint } from './SourceText'
import { gapPlace } from './textPlaceholders'
import { chunkHolding, textItems, type TextState } from './textState'
import { FIRST_BLOCK } from './useReviewWindow'
import css from './review.module.css'

/** Заглушку начинают грузить за экран до того, как она покажется — как в списке. */
const PREFETCH_MARGIN = '100% 0%'
const GAP_SELECTOR = '[data-text-gap]'
/** Что держит место в колонке: блоки текста и заглушки, в порядке чтения. */
const ANCHOR_SELECTOR = '[data-text-block], [data-text-gap]'

interface SourceTextsProps {
  /** Оглавление, загруженные куски и их подсветки. */
  text: TextState
  /** «Разобрана» из ответов ревью: сравнивается с подсветкой куска по ревизии. */
  done: ReadonlyMap<number, DoneMark>
  /** Карточка, чья фраза подсвечена: текущая или та, чью границу правят. */
  focused: StoredCandidate | null
  /** Источник фразы, чью границу правят: выделение принимает только его текст. */
  editingSourceId: number | null
  /** Кусок источника, где лежит блок (-1 — последний) или символ; true — ответ пришёл. */
  onLoad: (sourceId: number, place: TextPlace) => Promise<boolean>
  /** Кусок, где лежит блок, — если его ещё нет. */
  ensureBlock: (sourceId: number, block: number) => Promise<boolean>
  onWordClick: (candidateId: number) => void
  onTextSelected: (selected: SelectedText, point: SelectionPoint) => void
}

/** Прокрутка к фразе, которая ждёт свой кусок. */
interface PendingScroll {
  phraseId: number
  sourceId: number
  block: number
  smooth: boolean
}

/** Есть ли заглушка между словом и видимой частью колонки: плавная прокрутка грузила бы куски по пути. */
function gapBetween(container: HTMLElement, mark: HTMLElement): boolean {
  const view = container.getBoundingClientRect()
  const at = mark.getBoundingClientRect()
  const gaps = [...container.querySelectorAll(GAP_SELECTOR)].map(gap => gap.getBoundingClientRect())
  if (at.top > view.bottom) return gaps.some(gap => gap.bottom > view.top && gap.top < at.top)
  if (at.bottom < view.top) return gaps.some(gap => gap.top < view.bottom && gap.bottom > at.bottom)
  return false
}

/** Прокрутка к слову; останавливаемся на границе строки, чтобы верхняя видимая строка была целой. */
function scrollToMark(container: HTMLElement, mark: HTMLElement, smooth: boolean): void {
  const lineHeight = parseFloat(getComputedStyle(container).lineHeight)
  const top = Math.round((mark.offsetTop - container.clientHeight / 2) / lineHeight) * lineHeight
  container.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' })
}

/** Первый блок или заглушка, что видны сверху колонки: по ним держится место, когда выше догружается текст. */
function topBlock(container: HTMLElement): HTMLElement | null {
  const blocks = container.querySelectorAll<HTMLElement>(ANCHOR_SELECTOR)
  const top = container.getBoundingClientRect().top
  let low = 0
  let high = blocks.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (blocks[middle].getBoundingClientRect().bottom <= top) low = middle + 1
    else high = middle
  }
  return blocks[low] ?? null
}

/** Тексты всех источников набора подряд, у каждого заголовок; прокручиваются одной колонкой.
 * Когда текстов больше одного, каждый сворачивается до заголовка. Незагруженный текст — заглушки,
 * которые грузятся у экрана; загруженный остаётся. */
export function SourceTexts({ text, done, focused, editingSourceId, onLoad, ensureBlock, onWordClick, onTextSelected }: SourceTextsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const documents = text.contents?.documents ?? []
  const focusId = focused?.phrase_id ?? null
  const [folded, setFolded] = useState<ReadonlySet<number>>(new Set())
  const foldable = documents.length > 1

  // Клик по подсветке не перерисовывает куски: обработчик один на всё время.
  const clickRef = useRef(onWordClick)
  useEffect(() => { clickRef.current = onWordClick }, [onWordClick])
  const onMarkClick = useCallback((id: number) => clickRef.current(id), [])

  // Место в колонке держится по верхнему видимому блоку: догруженный выше текст её не сдвигает.
  const anchor = useRef<{ block: HTMLElement; top: number } | null>(null)
  const remember = useCallback(() => {
    const container = containerRef.current
    const block = container ? topBlock(container) : null
    anchor.current = block ? { block, top: block.getBoundingClientRect().top } : null
  }, [])
  useLayoutEffect(() => {
    const container = containerRef.current
    const held = anchor.current
    if (container && held?.block.isConnected) {
      const shift = held.block.getBoundingClientRect().top - held.top
      if (shift !== 0) container.scrollTop += shift
    }
    remember()
  }, [text, folded, remember])

  const scrollTo = useCallback((mark: HTMLElement, smooth: boolean) => {
    const container = containerRef.current
    if (!container) return
    scrollToMark(container, mark, smooth)
    remember()
  }, [remember])

  const pending = useRef<PendingScroll | null>(null)
  /** Сколько раз прокрутка к фразе закончилась: заглушки ждут её, чтобы не грузить текст под ней. */
  const [scrolled, setScrolled] = useState(0)
  const textRef = useRef(text)
  useLayoutEffect(() => { textRef.current = text }, [text])
  const focusedRef = useRef(focused)
  useLayoutEffect(() => { focusedRef.current = focused }, [focused])

  /** Прокрутки к фразе больше не ждём: заглушки снова грузятся. */
  const dropPending = useCallback(() => {
    if (pending.current === null) return
    pending.current = null
    setScrolled(n => n + 1)
  }, [])

  const toggle = (sourceId: number) => {
    // Свёрнутый документ не дорисует фразу, которую ждёт прокрутка.
    if (!folded.has(sourceId) && pending.current?.sourceId === sourceId) dropPending()
    setFolded(prev => {
      const next = new Set(prev)
      if (!next.delete(sourceId)) next.add(sourceId)
      return next
    })
  }

  /** Прокрутка, что ждала кусок фразы, — когда кусок нарисован. Слова нет и в нём — прокрутки нет. */
  const finishScroll = useCallback(() => {
    const wanted = pending.current
    const container = containerRef.current
    if (!wanted || !container || !chunkHolding(textRef.current, wanted.sourceId, wanted.block)) return
    const section = container.querySelector(`[data-source-id="${wanted.sourceId}"]`)
    // Кусок есть, но документ ещё не раскрыт: ждём, пока его текст нарисуется.
    if (!section?.querySelector(`[data-text-block="${wanted.block}"]`)) return
    pending.current = null
    const card = focusedRef.current
    const mark = card?.phrase_id === wanted.phraseId ? findMark(section, wanted.phraseId, card.source_phrase.text) : null
    if (mark) scrollTo(mark, wanted.smooth)
    setScrolled(n => n + 1)
  }, [scrollTo])
  useLayoutEffect(finishScroll)

  // Держим слово текущей фразы в видимой части колонки. Правка границы раскрывает документ своей фразы
  // и открывает текст на ней; у фразы без места (пример) текст остаётся, где был.
  const editingStarted = editingSourceId !== null
  useEffect(() => {
    const container = containerRef.current
    if (!container || focusId === null || !focused) return
    const sourceId = focused.source.id
    // У источника без документа текста нет: ни прокрутки, ни запроса.
    if (!textRef.current.contents?.documents.some(d => d.source_id === sourceId)) {
      dropPending()
      return
    }
    if (editingStarted) setFolded(prev => (prev.has(sourceId) ? new Set([...prev].filter(id => id !== sourceId)) : prev))
    else if (folded.has(sourceId)) {
      dropPending()
      return
    }
    const position = focused.phrase_position
    const section = container.querySelector(`[data-source-id="${sourceId}"]`)
    if (!position) {
      dropPending()
      if (editingStarted) {
        if (!textRef.current.chunks.has(sourceId)) void ensureBlock(sourceId, FIRST_BLOCK)
        return
      }
      const mark = section ? findMark(section, focusId, focused.source_phrase.text) : null
      if (mark) scrollTo(mark, !gapBetween(container, mark))
      return
    }
    const before = section?.querySelector<HTMLElement>(`[data-mark-id="${focusId}"]`) ?? null
    pending.current = { phraseId: focusId, sourceId, block: position.block, smooth: before !== null && !gapBetween(container, before) }
    void ensureBlock(sourceId, position.block).then(loaded => {
      if (!loaded && pending.current?.phraseId === focusId) dropPending()
    })
    finishScroll()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- прокручиваем при смене фразы и начале правки, а не при каждом обновлении текста
  }, [focusId, editingStarted])

  // Заглушка у экрана грузит кусок с того края, что к нему обращён; пока прокрутка ждёт кусок фразы — ничего.
  useEffect(() => {
    const container = containerRef.current
    if (!container || typeof IntersectionObserver === 'undefined' || pending.current) return
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting || pending.current) continue
        const gap = (entry.target as HTMLElement).dataset
        const place = gapPlace(
          { start: Number(gap.gapStart), end: gap.gapEnd === undefined ? null : Number(gap.gapEnd), startOffset: Number(gap.gapOffset) },
          entry.boundingClientRect,
          // Край — относительно самой колонки, а не поля подгрузки вокруг неё.
          container.getBoundingClientRect(),
        )
        void onLoad(Number(gap.sourceId), place)
      }
    }, { root: container, rootMargin: PREFETCH_MARGIN })
    container.querySelectorAll(GAP_SELECTOR).forEach(gap => observer.observe(gap))
    return () => observer.disconnect()
  }, [text, folded, scrolled, onLoad])

  return (
    <div ref={containerRef} className={css.source} onScroll={remember}>
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
                sourceId={document.source_id}
                items={textItems(text, document.source_id)}
                text={text}
                done={done}
                focused={focused}
                onWordClick={onMarkClick}
                onTextSelected={selectable ? onTextSelected : undefined}
              />
            )}
          </section>
        )
      })}
    </div>
  )
}
