import type { Closes } from '@/api/types'
import { rowIndexOf, type DoneMark, type ReviewState } from './reviewState'

/**
 * Нажатие, показанное до ответа сервера: экран сразу ставит отметки «разобрана», которые оставит нажатие
 * (что именно — говорит кнопка, `closes`), и переходит туда, куда перейдёт сервер: к первой неразобранной
 * карточке после нажатой в её участке списка, с начала участка, если после неё таких нет.
 * Ответ сервера главный: он ложится поверх и, если не совпал, ставит свой фокус.
 */
export interface PressAhead {
  pressed: number
  /** Куда перешёл экран; нажатая — если перейти, не зная строк, нельзя. */
  landed: number
  /** Отметки до нажатия у карточек, которые оно отметило. */
  before: ReadonlyMap<number, DoneMark | undefined>
  /** Отметка, которую поставило нажатие: ответ сервера её сменяет. */
  mark: DoneMark
}

/** Состояние сразу после нажатия и что оно поставило; null — нажатие ничего не закрывает, экран ждёт ответа. */
export function pressAhead(
  state: ReviewState, pressed: number, closes: Closes | null,
): { state: ReviewState; ahead: PressAhead } | null {
  const card = state.cards.get(pressed)
  if (closes === null || !card || doneOf(state, pressed)) return null
  const closed = closes === 'card'
    ? [pressed]
    : [...state.cards.values()].flatMap(c => (c.lemma === card.lemma ? [c.phrase_id] : []))
  const done = new Map(state.done)
  const before = new Map<number, DoneMark | undefined>()
  const mark: DoneMark = { done: true, revision: state.revision }
  for (const id of closed) {
    before.set(id, state.done.get(id))
    done.set(id, mark)
  }
  const marks = { ...state, done }
  const next = nextOpen(marks, pressed)
  const landed = next ?? pressed
  return { state: { ...marks, currentId: landed }, ahead: { pressed, landed, before, mark } }
}

/** Отметки нажатия, которое сервер отклонил, — назад; экран — на нажатую, если с места перехода не уходили. */
export function undoAhead(state: ReviewState, ahead: PressAhead): ReviewState {
  const done = new Map(state.done)
  for (const [id, before] of ahead.before) {
    if (done.get(id) !== ahead.mark) continue
    if (before === undefined) done.delete(id)
    else done.set(id, before)
  }
  return { ...state, done, currentId: state.currentId === ahead.landed ? ahead.pressed : state.currentId }
}

/** Разобрана ли карточка; undefined — карточки нет среди загруженных. */
function doneOf(state: ReviewState, phraseId: number): boolean | undefined {
  return state.done.get(phraseId)?.done ?? state.cards.get(phraseId)?.is_done
}

/**
 * Первая неразобранная карточка участка после нажатой, затем с начала участка; участок — строки карточек
 * между строками разделов. null — открытых нет; undefined — путь к ней идёт через незагруженное.
 */
function nextOpen(state: ReviewState, pressed: number): number | null | undefined {
  const index = rowIndexOf(state, pressed)
  if (index === undefined) return undefined
  const after = firstOpen(state, index + 1, () => true)
  if (after !== null) return after
  let start = index
  for (let i = index - 1; i >= 0; i--) {
    const row = state.rows.get(i)
    if (!row) return undefined
    if (row.phrase_id === null) break
    start = i
  }
  return firstOpen(state, start, i => i < index)
}

/** Первая неразобранная карточка от строки вниз до строки раздела, края списка или `within`. */
function firstOpen(state: ReviewState, start: number, within: (index: number) => boolean): number | null | undefined {
  for (let i = start; i < state.totalRows && within(i); i++) {
    const row = state.rows.get(i)
    if (!row) return undefined
    if (row.phrase_id === null) return null
    const done = doneOf(state, row.phrase_id)
    if (done === undefined) return undefined
    if (!done) return row.phrase_id
  }
  return null
}
