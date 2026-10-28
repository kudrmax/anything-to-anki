import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  BLOCK_ATTR, CardLayoutEditingContext, CardLayoutViewContext, ROW_ATTR, type CardLayoutEditing, type DragItem,
} from '@/cardLayout'
import type { CardElement } from '@/api/types'
import { SETTINGS_PATH } from '@/shell'
import { ReviewView } from '@/screens/review/ReviewScreen'
import { ReviewApiContext } from '@/screens/review/reviewApi'
import { EditorWindow } from './EditorWindow'
import { LeaveCheck } from './LeaveCheck'
import { ELEMENT_LABEL } from './labels'
import { EDITOR_WINDOW_ATTR, editFor, type DropTarget } from './layoutDrag'
import { CARD_LAYOUT_PATH, PHONE_FRAME, PHONE_FRAME_PARAM } from './paths'
import { pictureSuggestionsShownPref } from '@/lib/preferences'
import { DEFAULT_SAMPLE_PARTS, samplePartsKey, toggleSamplePart, type SamplePart } from './sampleParts'
import { SAMPLE_SCOPE, sampleReviewApi } from './sampleReview'
import { useBlockedActions } from './useBlockedActions'
import { useCardLayoutEditor } from './useCardLayoutEditor'
import { useLayoutDrag } from './useLayoutDrag'
import css from './cardLayoutEditor.module.css'

const SETTINGS_SECTION = `${SETTINGS_PATH}?section=cards`
/** Экран образца: его ссылки гасит сам образец, их выход из редактора не касается. */
const SAMPLE_SCREEN_ATTR = 'data-sample-screen'
/** Щелчок мимо блоков, линий и окна редактора снимает выбор: карточка видна такой, какой будет. */
const KEEPS_SELECTION = `[${BLOCK_ATTR}], [${ROW_ATTR}], [${EDITOR_WINDOW_ATTR}]`

/** Экран ревью на образце: тот же код, что у ревью; решать на нём нечего, работают только кнопки вида. */
function SampleReview({ parts }: { parts: ReadonlySet<SamplePart> }) {
  const screenRef = useRef<HTMLDivElement>(null)
  useBlockedActions(screenRef)
  const api = useMemo(() => sampleReviewApi(parts), [parts])
  return (
    <ReviewApiContext.Provider value={api}>
      <div ref={screenRef} className={css.screen} {...{ [SAMPLE_SCREEN_ATTR]: '' }}>
        <ReviewView scope={SAMPLE_SCOPE} requestedId={null} />
      </div>
    </ReviewApiContext.Provider>
  )
}

/** Тот же экран в рамке телефона: настоящие телефонные стили работают только в окне шириной с телефон. */
function PhoneReview() {
  return (
    <div className={css.phoneStage}>
      <iframe className={css.phoneFrame} title="The review on a phone" src={`${CARD_LAYOUT_PATH}?${PHONE_FRAME_PARAM}=${PHONE_FRAME}`} />
    </div>
  )
}

/**
 * Редактор раскладки карточки — экран ревью целиком, на образце. Блоки и линии карточки тянутся и выбираются
 * прямо на нём, остальное — в окне поверх. Каждая правка сразу сохраняется и сразу видна на карточке.
 */
export function CardLayoutEditorScreen() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const editor = useCardLayoutEditor()
  const { view, selection, select, edit } = editor
  const rootRef = useRef<HTMLElement | null>(null)
  const [phone, setPhone] = useState(false)
  const [parts, setParts] = useState(DEFAULT_SAMPLE_PARTS)
  /** Куда уходят из редактора, пока ждём ответа про скрытые блоки. */
  const [leavingTo, setLeavingTo] = useState<string | null>(null)
  const hiddenBlocks = view?.hidden ?? []
  const hasHidden = hiddenBlocks.length > 0
  const leave = useCallback((path: string) => {
    if (hasHidden) setLeavingTo(path)
    else navigate(path)
  }, [hasHidden, navigate])

  // Ссылки приложения вне образца (вкладки сверху) тоже уводят из редактора: со скрытыми блоками — через вопрос.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const link = e.target instanceof Element ? e.target.closest('a[href]') : null
      if (!link || link.closest(`[${SAMPLE_SCREEN_ATTR}]`) || !hasHidden) return
      e.preventDefault()
      e.stopPropagation()
      setLeavingTo(new URL((link as HTMLAnchorElement).href).pathname)
    }
    document.addEventListener('click', onClick, true)
    return () => document.removeEventListener('click', onClick, true)
  }, [hasHidden])
  // Подобранные картинки на ревью видны, когда включены их подсказки: выбор картинки их и включает, как кнопка в шапке.
  const togglePart = (part: SamplePart) => {
    const next = toggleSamplePart(parts, part)
    if (next.has('picture_choice')) pictureSuggestionsShownPref.write(true)
    setParts(next)
  }

  const onClick = useCallback((item: DragItem) => {
    if (item.kind === 'block') select({ kind: 'block', element: item.element })
    else if (item.kind === 'divider') select({ kind: 'divider', column: item.column, row: item.row })
  }, [select])
  // Блок после броска остаётся выбранным; место линии после броска другое — выбор с неё снимается.
  const onDrop = useCallback((item: DragItem, target: DropTarget) => {
    const change = editFor(item, target)
    if (!change) return
    if (item.kind === 'block') select({ kind: 'block', element: item.element })
    else select(null)
    void edit(change)
  }, [select, edit])
  const canHide = useCallback(
    (element: CardElement) => view?.elements.find(entry => entry.element === element)?.can_hide ?? true,
    [view],
  )
  const { drag, start } = useLayoutDrag(rootRef, onDrop, onClick, canHide)

  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      if (!(e.target instanceof Element) || !e.target.closest(KEEPS_SELECTION)) select(null)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') select(null) }
    window.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [select])

  const editing = useMemo<CardLayoutEditing>(() => ({
    selection,
    dragged: drag?.item ?? null,
    startDrag: start,
    select: onClick,
    labelOf: element => ELEMENT_LABEL[element],
    setRoot: root => { rootRef.current = root },
  }), [selection, drag, start, onClick])

  if (params.get(PHONE_FRAME_PARAM) === PHONE_FRAME) return <SampleReview parts={DEFAULT_SAMPLE_PARTS} />

  const target = drag?.target
  const line = target && target.kind !== 'tray' ? target.line : null

  return (
    <CardLayoutViewContext.Provider value={view}>
      <CardLayoutEditingContext.Provider value={editing}>
        {phone ? <PhoneReview /> : <SampleReview key={samplePartsKey(parts)} parts={parts} />}
        <EditorWindow
          editor={editor}
          parts={parts}
          onTogglePart={togglePart}
          startDrag={start}
          trayActive={target?.kind === 'tray'}
          phone={phone}
          onTogglePhone={() => setPhone(on => !on)}
          onDone={() => leave(SETTINGS_SECTION)}
        />
        {line && (
          <span
            className={css.dropLine}
            style={{ '--x': `${line.x}px`, '--y': `${line.y}px`, '--w': `${line.width}px`, '--hh': `${line.height}px` } as CSSProperties}
          />
        )}
        {drag && (
          <span className={css.ghost} style={{ '--gx': `${drag.x}px`, '--gy': `${drag.y}px` } as CSSProperties}>
            {drag.item.kind === 'block' ? ELEMENT_LABEL[drag.item.element] : 'Divider'}
          </span>
        )}
        {leavingTo && (
          <LeaveCheck hidden={hiddenBlocks} onStay={() => setLeavingTo(null)} onLeave={() => navigate(leavingTo)} />
        )}
      </CardLayoutEditingContext.Provider>
    </CardLayoutViewContext.Provider>
  )
}
