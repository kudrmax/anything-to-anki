import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, ReviewExpiredError } from '@/api/client'
import type { CandidateSection, Closes, GenerationOverview, ReviewContext, ReviewUpdate, SetScope, StoredCandidate, TextPlace } from '@/api/types'
import type { SortOrder } from '@/lib/preferences'
import {
  applyUpdate, currentRow, initialState, missesReplace, neighbour, reopened, rowIndexOf, withCurrent,
  type ApplyOptions, type ReviewState,
} from './reviewState'
import { pressAhead, undoAhead, type PressAhead } from './pressAhead'
import { applyText, chunkHolding, chunkRefs, initialText, withContents, type TextState } from './textState'

export const POLL_INTERVAL_MS = 3000
/** Сколько строк списка просить за раз: сколько грузить, а не правило. */
export const ROWS_PER_FETCH = 50
/** Высота свёрнутой строки, пока её нет: заглушка держит место под незагруженные строки. */
export const ROW_ESTIMATE_PX = 50
/** Через сколько после перехода сервер узнаёт новую текущую: переход мгновенный, листание не шлёт запрос на каждый шаг. */
const CURRENT_SYNC_DELAY_MS = 200
/** Проверок соседа: до загрузки строк, после неё и после повторной, если ответ строк устарел. */
const STEP_ATTEMPTS = 3
/** Первый кусок документа и последний (сервер понимает -1 как последний блок). */
export const FIRST_BLOCK = 0
export const LAST_BLOCK = -1
const NOT_FOUND = 404

export type ReviewCall<T> = (ctx: ReviewContext) => Promise<T>

const isNotFound = (e: unknown): boolean => e instanceof ApiError && e.status === NOT_FOUND

const contextOf = (state: ReviewState): ReviewContext | null =>
  state.reviewId === null ? null : { review_id: state.reviewId, since: state.revision, current: state.currentId }

/** Нажатие кнопки решения: экран переходит сразу, не дожидаясь ответа. */
export interface Press {
  phraseId: number
  closes: Closes | null
}

interface PendingRows {
  start: number
  end: number
  done: Promise<boolean>
}

/**
 * Открытое ревью набора: сервер держит порядок, клиент — загруженные окна строк.
 * Каждый запрос шлёт ревизию клиента и текущую карточку; истёкшее ревью открывается заново на текущей.
 */
export function useReviewWindow(scope: SetScope, sortOrder: SortOrder, requestedId: number | null) {
  const [state, setState] = useState<ReviewState>(initialState)
  const stateRef = useRef(state)
  const commit = useCallback((change: (s: ReviewState) => ReviewState): boolean => {
    const next = change(stateRef.current)
    if (next === stateRef.current) return false
    stateRef.current = next
    setState(next)
    return true
  }, [])
  const [loading, setLoading] = useState(true)
  const [gone, setGone] = useState(false)
  const [text, setText] = useState<TextState>(initialText)
  const textRef = useRef(text)
  const commitText = useCallback((change: (t: TextState) => TextState) => {
    const next = change(textRef.current)
    if (next === textRef.current) return
    textRef.current = next
    setText(next)
  }, [])
  const [generation, setGeneration] = useState<GenerationOverview | null>(null)
  /** Разделы, которые раскрыл пользователь: ревью, открытое заново, раскрывает их же. */
  const openedSections = useRef<Set<CandidateSection>>(new Set())

  /** Окно вокруг текущей: после пропущенного replace у клиента только строки новой раскладки из ответа. */
  const recenter = useRef<() => void>(() => {})
  /** Оглавление не того ревью или не той версии: его просят заново. */
  const checkContents = useRef<(update: ReviewUpdate) => void>(() => {})
  const refreshContents = useRef<() => void>(() => {})
  const apply = useCallback((update: ReviewUpdate, options: ApplyOptions = {}): boolean => {
    const missed = missesReplace(stateRef.current, update)
    // Подсветки ложатся из каждого ответа, даже устаревшего: сервер не пришлёт их ещё раз.
    commitText(t => applyText(t, update))
    const applied = commit(s => applyUpdate(s, update, options))
    const held = stateRef.current
    // Новый список без строки текущей карточки: строки вокруг неё просим отдельно.
    const lost = update.layout?.replace === true && held.currentId !== null
      && held.cards.has(held.currentId) && rowIndexOf(held, held.currentId) === undefined
    if (applied && (missed || lost)) recenter.current()
    checkContents.current(update)
    return applied
  }, [commit, commitText])

  const openAt = useCallback((requested: number | null) => api.openReview({
    scope: String(scope),
    sort: sortOrder,
    requested_id: requested,
    open_sections: [...openedSections.current],
    text_chunks: chunkRefs(textRef.current),
  }), [scope, sortOrder])

  const applyOpened = useCallback((update: ReviewUpdate) => {
    commitText(t => applyText(t, update))
    commit(s => reopened(s, update))
    checkContents.current(update)
  }, [commit, commitText])

  const reopening = useRef<Promise<void> | null>(null)
  const reopen = useCallback((expiredId: string): Promise<void> => {
    if (stateRef.current.reviewId !== expiredId) return reopening.current ?? Promise.resolve()
    reopening.current ??= openAt(stateRef.current.currentId)
      .then(applyOpened)
      .finally(() => { reopening.current = null })
    return reopening.current
  }, [openAt, applyOpened])

  /** Запрос к открытому ревью; истёкшее ревью открывается заново на текущей карточке, запрос уходит ещё раз. */
  const send = useCallback(async <T>(call: ReviewCall<T>): Promise<T> => {
    const ctx = contextOf(stateRef.current)
    if (!ctx) throw new Error('The review is not open')
    try {
      return await call(ctx)
    } catch (e) {
      if (!(e instanceof ReviewExpiredError)) throw e
      await reopen(ctx.review_id)
      return call(contextOf(stateRef.current)!)
    }
  }, [reopen])

  /** Нажатия уходят на сервер по одному, в порядке нажатий: следующее — после ответа на предыдущее. */
  const presses = useRef<Promise<unknown>>(Promise.resolve())
  /** Леммы, которые решают нажатия в очереди: сколько таких нажатий ещё не получило ответ. */
  const closing = useRef(new Map<string, number>())

  /**
   * Единственный путь изменения на экране ревью: ответ ложится на состояние, фокус — куда сказал сервер.
   * Нажатие (`press`) показывается сразу: отметки и переход — до ответа, сам запрос — в фоне, в очереди нажатий;
   * ответ главный — если экран всё ещё там, куда перешёл, а сервер поставил фокус иначе, фокус ставит ответ.
   * Отклонённое нажатие снимает свои отметки и возвращает экран на нажатую карточку.
   * Ошибку, кроме истёкшего ревью, получает вызывающий: он показывает её, как раньше.
   */
  const mutate = useCallback(async (call: ReviewCall<ReviewUpdate>, press?: Press): Promise<ReviewUpdate> => {
    let ahead: PressAhead | null = null
    if (press) {
      const shown = pressAhead(stateRef.current, press.phraseId, press.closes, new Set(closing.current.keys()))
      if (shown) {
        ahead = shown.ahead
        commit(() => shown.state)
        if (ahead.lemma !== null) closing.current.set(ahead.lemma, (closing.current.get(ahead.lemma) ?? 0) + 1)
      }
    }
    const lemma = ahead?.lemma ?? null
    // Ответ пришёл (или нажатие отклонено): сервер сам говорит, что разобрано.
    const settled = () => {
      if (lemma === null) return
      const left = (closing.current.get(lemma) ?? 1) - 1
      if (left > 0) closing.current.set(lemma, left)
      else closing.current.delete(lemma)
    }
    let update: ReviewUpdate
    try {
      if (press) {
        const turn = presses.current.catch(() => {}).then(() => send(call))
        presses.current = turn
        update = await turn
      } else {
        update = await send(call)
      }
    } catch (e) {
      settled()
      const undone = ahead
      if (undone) commit(s => undoAhead(s, undone))
      throw e
    }
    const stale = update.revision < stateRef.current.revision
    // Экран ушёл с места перехода — дальше ведёт он; остался — фокус ставит ответ.
    const leftBehind = ahead !== null && stateRef.current.currentId !== ahead.landed
    apply(update, { keepCurrent: ahead !== null })
    settled()
    const focus = update.focus_id
    if (leftBehind || focus === null) return update
    // Опрос мог обогнать нажатие: устаревший ответ ничего не меняет, но фокус нажатия не теряется.
    if (ahead !== null || stale) {
      if (!stale || rowIndexOf(stateRef.current, focus) !== undefined) commit(s => withCurrent(s, focus))
    }
    return update
  }, [send, apply, commit])

  const loadGeneration = useCallback(async () => {
    try {
      setGeneration(await api.getReviewGeneration(scope))
    } catch {
      // Панель генерации просто не покажет свежие числа до следующей попытки.
    }
  }, [scope])

  // Открытие — на карточке ссылки, после смены сортировки — на текущей; ✨ грузится рядом и его не ждёт,
  // текст — после открытия, по оглавлению.
  useEffect(() => {
    let live = true
    void loadGeneration()
    openAt(stateRef.current.currentId ?? requestedId)
      .then(update => {
        if (!live) return
        applyOpened(update)
        setGone(false)
      })
      .catch(() => { if (live) setGone(true) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [openAt, applyOpened, loadGeneration, requestedId])

  const pending = useRef<PendingRows[]>([])
  /** Строки [start, start + count); true — ответ пришёл. Тот же участок дважды не просит. */
  const loadRows = useCallback((start: number, count: number): Promise<boolean> => {
    const end = start + count
    const covering = pending.current.find(p => p.start <= start && end <= p.end)
    if (covering) return covering.done
    const entry: PendingRows = { start, end, done: Promise.resolve(false) }
    entry.done = send(ctx => api.reviewRows(ctx, start, count))
      .then(update => { apply(update, { window: true }); return true })
      .catch(e => { if (isNotFound(e)) setGone(true); return false })
      .finally(() => { pending.current = pending.current.filter(p => p !== entry) })
    pending.current.push(entry)
    return entry.done
  }, [send, apply])

  const pendingText = useRef(new Map<string, Promise<boolean>>())
  /** Кусок источника, где лежит блок или символ; true — ответ пришёл. Тот же запрос дважды разом не уходит. */
  const loadText = useCallback((sourceId: number, place: TextPlace): Promise<boolean> => {
    const key = `${sourceId}:${'at' in place ? `@${place.at}` : place.block}`
    const asked = pendingText.current.get(key)
    if (asked) return asked
    const done = send(ctx => api.reviewText(ctx, sourceId, place))
      .then(update => { apply(update, { window: true }); return true })
      .catch(e => {
        // Источник ушёл из набора: оглавление это скажет.
        if (isNotFound(e)) refreshContents.current()
        return false
      })
      .finally(() => { pendingText.current.delete(key) })
    pendingText.current.set(key, done)
    return done
  }, [send, apply])

  /** Кусок, где лежит блок, — если его ещё нет. */
  const ensureBlock = useCallback(async (sourceId: number, block: number): Promise<boolean> => {
    if (chunkHolding(textRef.current, sourceId, block)) return true
    return loadText(sourceId, { block })
  }, [loadText])

  // Первый текст ревью: кусок у текущей карточки, без неё — начало первого документа.
  const loadFirstText = useCallback(() => {
    const contents = textRef.current.contents
    if (!contents || textRef.current.chunks.size > 0) return
    const card = stateRef.current.currentId === null ? undefined : stateRef.current.cards.get(stateRef.current.currentId)
    const position = card?.phrase_position
    if (card && position && contents.documents.some(d => d.source_id === card.source.id)) {
      void loadText(card.source.id, { block: position.block })
    } else if (contents.documents.length > 0) {
      void loadText(contents.documents[0].source_id, { block: FIRST_BLOCK })
    }
  }, [loadText])

  const contentsRequest = useRef<Promise<void> | null>(null)
  useEffect(() => {
    const refresh = () => {
      if (contentsRequest.current) return
      if (stateRef.current.reviewId === null) return
      let reviewId = ''
      contentsRequest.current = send(ctx => { reviewId = ctx.review_id; return api.reviewContents(ctx) })
        .then(contents => {
          commitText(t => withContents(t, contents, reviewId))
          loadFirstText()
        })
        .catch(() => {
          // Без оглавления текст не показывается до следующего ответа другой версии.
        })
        .finally(() => { contentsRequest.current = null })
    }
    refreshContents.current = refresh
    checkContents.current = (update: ReviewUpdate) => {
      if (update.review_id !== stateRef.current.reviewId) return
      const held = textRef.current
      // Версия ниже той, что есть, — ответ устарел: оглавление новее него.
      if (held.contents !== null && held.reviewId === update.review_id && update.contents_version <= held.contents.version) return
      // Пока оглавление в пути, ответ другой версии проверяется ещё раз после него.
      if (contentsRequest.current) void contentsRequest.current.then(() => checkContents.current(update))
      else refresh()
    }
  }, [send, commitText, loadFirstText])

  useEffect(() => {
    recenter.current = () => {
      const id = stateRef.current.currentId
      if (id === null) return
      // Строки для экрана, а не переход: пока они шли, экран мог уйти дальше.
      send(ctx => api.reviewAround(ctx, id))
        .then(update => { apply(update, { window: true, keepCurrent: true }) })
        .catch(e => { if (isNotFound(e)) setGone(true) })
    }
  }, [send, apply])

  // Сервер раскрывает раздел текущей карточки сам: ушли с неё — он узнаёт об этом сразу после перехода,
  // а ответ сворачивает раздел, если список изменился. Переход не ждёт ответа.
  const syncTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(syncTimer.current), [])
  const moveTo = useCallback((phraseId: number) => {
    if (!commit(s => withCurrent(s, phraseId))) return
    clearTimeout(syncTimer.current)
    syncTimer.current = setTimeout(() => {
      send(ctx => api.reviewChanges(ctx))
        .then(update => { apply(update) })
        .catch(e => { if (isNotFound(e)) setGone(true) })
    }, CURRENT_SYNC_DELAY_MS)
  }, [commit, send, apply])

  /** К карточке: загруженная становится текущей сразу, дальняя приходит с окном вокруг неё. */
  const goTo = useCallback(async (phraseId: number) => {
    if (rowIndexOf(stateRef.current, phraseId) !== undefined) {
      moveTo(phraseId)
      return
    }
    const around = async () => { apply(await send(ctx => api.reviewAround(ctx, phraseId)), { window: true }) }
    await around()
    // Ответ, который обогнало изменение, устарел: окно просим ещё раз.
    if (stateRef.current.currentId !== phraseId) await around()
  }, [send, apply, moveTo])

  /** Соседняя карточка видимого списка; строки рядом догружаются, если их ещё нет. Шаги идут по очереди. */
  const stepping = useRef<Promise<void>>(Promise.resolve())
  const stepOnce = useCallback(async (delta: 1 | -1) => {
    for (let attempt = 0; attempt < STEP_ATTEMPTS; attempt++) {
      const target = neighbour(stateRef.current, delta)
      if (target === null) return
      if (target !== undefined) {
        moveTo(target)
        return
      }
      const index = rowIndexOf(stateRef.current, stateRef.current.currentId)
      if (index === undefined) return
      const start = delta > 0 ? index + 1 : Math.max(0, index - ROWS_PER_FETCH)
      // Устаревший ответ строк не ложится: тогда просим их ещё раз.
      await loadRows(start, delta > 0 ? ROWS_PER_FETCH : index - start)
    }
  }, [loadRows, moveTo])
  const step = useCallback((delta: 1 | -1): Promise<void> => {
    stepping.current = stepping.current.catch(() => {}).then(() => stepOnce(delta))
    return stepping.current
  }, [stepOnce])

  const toggleSection = useCallback(async (section: CandidateSection, isOpen: boolean) => {
    const open = !isOpen
    if (open) openedSections.current.add(section)
    else openedSections.current.delete(section)
    apply(await send(ctx => api.setReviewSection(ctx, section, open)), { window: true })
  }, [send, apply])

  const poll = useCallback(async (withGeneration: boolean) => {
    try {
      apply(await send(ctx => api.reviewChanges(ctx)))
    } catch (e) {
      if (isNotFound(e)) setGone(true)
      return
    }
    if (withGeneration) await loadGeneration()
  }, [send, apply, loadGeneration])

  // Пока идёт генерация или источник набора занят операцией, ревью спрашивает, что изменилось.
  const inProgress = generation?.in_progress ?? false
  const busy = state.header?.busy ?? false
  useEffect(() => {
    if (!inProgress && !busy) return
    const interval = setInterval(() => void poll(inProgress), POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [inProgress, busy, poll])

  const current: StoredCandidate | null = state.currentId === null ? null : state.cards.get(state.currentId) ?? null
  const row = currentRow(state)
  const position = row?.position ?? null

  /** Карточка из загруженных: её данные читают действия. */
  const cardOf = useCallback((phraseId: number): StoredCandidate | undefined => stateRef.current.cards.get(phraseId), [])

  return {
    state, loading, gone, generation, loadGeneration,
    current, position, canPrev: position !== null && position > 1, canNext: position !== null && position < state.totalCards,
    cardOf,
    text, hasSourceText: (text.contents?.documents.length ?? 0) > 0, loadText, ensureBlock,
    loadRows, goTo, step, toggleSection, mutate,
  }
}

export type ReviewWindow = ReturnType<typeof useReviewWindow>
