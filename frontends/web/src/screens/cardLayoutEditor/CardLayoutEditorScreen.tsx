import { useCallback, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  CardLayoutEditingContext, CardLayoutViewContext, type CardLayoutEditing, type DragItem,
} from '@/cardLayout'
import { SETTINGS_PATH } from '@/shell'
import { ReviewView } from '@/screens/review/ReviewScreen'
import { ReviewApiContext } from '@/screens/review/reviewApi'
import { EditorWindow } from './EditorWindow'
import { ELEMENT_LABEL } from './labels'
import { editFor, type DropTarget } from './layoutDrag'
import { CARD_LAYOUT_PATH, PHONE_FRAME, PHONE_FRAME_PARAM } from './paths'
import { SAMPLE_REVIEW_API, SAMPLE_SCOPE } from './sampleReview'
import { useBlockedActions } from './useBlockedActions'
import { useCardLayoutEditor } from './useCardLayoutEditor'
import { useLayoutDrag } from './useLayoutDrag'
import css from './cardLayoutEditor.module.css'

const SETTINGS_SECTION = `${SETTINGS_PATH}?section=card-layout`

/** Экран ревью на образце: тот же код, что у ревью; решать на нём нечего, работают только кнопки вида. */
function SampleReview() {
  const screenRef = useRef<HTMLDivElement>(null)
  useBlockedActions(screenRef)
  return (
    <ReviewApiContext.Provider value={SAMPLE_REVIEW_API}>
      <div ref={screenRef} className={css.screen}>
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
  const { drag, start } = useLayoutDrag(rootRef, onDrop, onClick)

  const editing = useMemo<CardLayoutEditing>(() => ({
    selection,
    dragged: drag?.item ?? null,
    startDrag: start,
    select: onClick,
    labelOf: element => ELEMENT_LABEL[element],
    setRoot: root => { rootRef.current = root },
  }), [selection, drag, start, onClick])

  if (params.get(PHONE_FRAME_PARAM) === PHONE_FRAME) return <SampleReview />

  const target = drag?.target
  const line = target && target.kind !== 'tray' ? target.line : null

  return (
    <CardLayoutViewContext.Provider value={view}>
      <CardLayoutEditingContext.Provider value={editing}>
        {phone ? <PhoneReview /> : <SampleReview />}
        <EditorWindow
          editor={editor}
          startDrag={start}
          trayActive={target?.kind === 'tray'}
          phone={phone}
          onTogglePhone={() => setPhone(on => !on)}
          onDone={() => navigate(SETTINGS_SECTION)}
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
      </CardLayoutEditingContext.Provider>
    </CardLayoutViewContext.Provider>
  )
}
