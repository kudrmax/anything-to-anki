import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, ReviewExpiredError } from '@/api/client'
import type { CandidateSection, GenerationOverview, ReviewContext, ReviewUpdate, SetScope, SourceDocument, StoredCandidate } from '@/api/types'
import type { SortOrder } from '@/lib/preferences'
import {
  applyUpdate, currentRow, doneMarks, forgetDone, initialState, missesReplace, neighbour, reopened, rowIndexOf, withCurrent,
  type ApplyOptions, type ReviewState,
} from './reviewState'

export const POLL_INTERVAL_MS = 3000
/** Сколько строк списка просить за раз: сколько грузить, а не правило. */
export const ROWS_PER_FETCH = 50
/** Высота свёрнутой строки, пока её нет: заглушка держит место под незагруженные строки. */
export const ROW_ESTIMATE_PX = 50
/** Через сколько после перехода сервер узнаёт новую текущую: переход мгновенный, листание не шлёт запрос на каждый шаг. */
const CURRENT_SYNC_DELAY_MS = 200
/** Проверок соседа: до загрузки строк, после неё и после повторной, если ответ строк устарел. */
const STEP_ATTEMPTS = 3
const NOT_FOUND = 404
const AI_UNAVAILABLE = 503

export type ReviewCall<T> = (ctx: ReviewContext) => Promise<T>

/** Сбой AI-ручки потому, что AI недоступен отсюда (нужен VPN). */
export const isAiUnavailable = (e: unknown): boolean => e instanceof ApiError && e.status === AI_UNAVAILABLE

const isNotFound = (e: unknown): boolean => e instanceof ApiError && e.status === NOT_FOUND

const contextOf = (state: ReviewState): ReviewContext | null =>
  state.reviewId === null ? null : { review_id: state.reviewId, since: state.revision, current: state.currentId }

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
  const [documents, setDocuments] = useState<SourceDocument[]>([])
  const [generation, setGeneration] = useState<GenerationOverview | null>(null)
  const [aiBlocked, setAiBlocked] = useState(false)
  /** Разделы, которые раскрыл пользователь: ревью, открытое заново, раскрывает их же. */
  const openedSections = useRef<Set<CandidateSection>>(new Set())

  /** Окно вокруг текущей: после пропущенного replace у клиента только строки новой раскладки из ответа. */
  const recenter = useRef<() => void>(() => {})
  const apply = useCallback((update: ReviewUpdate, options: ApplyOptions = {}): boolean => {
    const missed = missesReplace(stateRef.current, update)
    const fresh = update.revision >= stateRef.current.revision
    const applied = commit(s => applyUpdate(s, update, options))
    if (applied && fresh && update.header.ai_unavailable) setAiBlocked(true)
    if (applied && missed) recenter.current()
    return applied
  }, [commit])

  const openAt = useCallback((requested: number | null) => api.openReview({
    scope: String(scope),
    sort: sortOrder,
    requested_id: requested,
    open_sections: [...openedSections.current],
  }), [scope, sortOrder])

  const applyOpened = useCallback((update: ReviewUpdate) => {
    commit(s => reopened(s, update))
    if (update.header.ai_unavailable) setAiBlocked(true)
  }, [commit])

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

  /**
   * Единственный путь изменения на экране ревью: ответ ложится на состояние, фокус — куда сказал сервер.
   * Ошибку, кроме истёкшего ревью, получает вызывающий: он показывает её, как раньше.
   */
  const mutate = useCallback(async (call: ReviewCall<ReviewUpdate>): Promise<ReviewUpdate> => {
    const update = await send(call)
    const stale = update.revision < stateRef.current.revision
    apply(update)
    // Опрос мог обогнать нажатие: устаревший ответ ничего не меняет, но фокус нажатия не теряется.
    if (stale && update.focus_id !== null && rowIndexOf(stateRef.current, update.focus_id) !== undefined) {
      const focus = update.focus_id
      commit(s => withCurrent(s, focus))
    }
    return update
  }, [send, apply, commit])

  const loadDocuments = useCallback(async () => {
    const upTo = stateRef.current.revision
    setDocuments(await api.getReviewDocuments(scope).catch(() => []))
    commit(s => forgetDone(s, upTo))
  }, [scope, commit])

  const loadGeneration = useCallback(async () => {
    try {
      setGeneration(await api.getReviewGeneration(scope))
    } catch {
      // Панель генерации просто не покажет свежие числа до следующей попытки.
    }
  }, [scope])

  // Открытие — на карточке ссылки, после смены сортировки — на текущей; тексты и ✨ грузятся рядом и его не ждут.
  useEffect(() => {
    let live = true
    void loadDocuments()
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
  }, [openAt, applyOpened, loadDocuments, loadGeneration, requestedId])

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

  useEffect(() => {
    recenter.current = () => {
      const id = stateRef.current.currentId
      if (id === null) return
      send(ctx => api.reviewAround(ctx, id))
        .then(update => { apply(update, { window: true }) })
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

  const poll = useCallback(async (withGeneration: boolean, withDocuments: boolean) => {
    try {
      apply(await send(ctx => api.reviewChanges(ctx)))
    } catch (e) {
      if (isNotFound(e)) setGone(true)
      return
    }
    // Rebuild и Refresh меняют тексты: их перечитываем после изменений.
    if (withDocuments) await loadDocuments()
    if (withGeneration) await loadGeneration()
  }, [send, apply, loadDocuments, loadGeneration])

  // Пока идёт генерация или источник набора занят операцией, ревью спрашивает, что изменилось.
  const inProgress = generation?.in_progress ?? false
  const busy = state.header?.busy ?? false
  useEffect(() => {
    if (!inProgress && !busy) return
    const interval = setInterval(() => void poll(inProgress, busy), POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [inProgress, busy, poll])

  const current: StoredCandidate | null = state.currentId === null ? null : state.cards.get(state.currentId) ?? null
  const row = currentRow(state)
  const position = row?.position ?? null
  const done = useMemo(() => doneMarks(state), [state])

  /** Карточка из загруженных: её данные читают действия. */
  const cardOf = useCallback((phraseId: number): StoredCandidate | undefined => stateRef.current.cards.get(phraseId), [])

  return {
    state, loading, gone, documents, generation, loadDocuments, loadGeneration,
    current, position, canPrev: position !== null && position > 1, canNext: position !== null && position < state.totalCards,
    done, cardOf,
    aiBlocked, showAiBlocked: () => setAiBlocked(true), dismissAiBlocked: () => setAiBlocked(false),
    loadRows, goTo, step, toggleSection, mutate,
  }
}

export type ReviewWindow = ReturnType<typeof useReviewWindow>
