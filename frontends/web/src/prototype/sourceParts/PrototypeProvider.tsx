// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { useCallback, useMemo, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { BANK_FOR_KIND, buildSentences, initialSources, sentencesFromText, type CardStatus, type Scope, type Source, type TakeOrder } from './mockData'
import { cardsIn, defaultOrder, takeMore, wordsLeft } from './model'
import { PrototypeContext, type GenKind, type GenMode, type PrototypeApi, type SourcePrefs, type TakeCount } from './prototypeContext'

const REBUILD_MS = 1000
const GENERATE_MS = 1500
const DEFAULT_COUNT = 100
const ADDED_PART_SIZE = 60

function initialScope(source: Source): Scope {
  const withCards = source.parts.filter(p => source.cards.some(c => c.partId === p.id))
  return (withCards.at(-1) ?? source.parts[0]).id
}

export function PrototypeProvider() {
  const [sources, setSources] = useState<Source[]>(initialSources)
  const [prefs, setPrefs] = useState<Record<string, SourcePrefs>>({})
  const [rebuildingIds, setRebuildingIds] = useState<ReadonlySet<string>>(new Set())
  const [runningKinds, setRunningKinds] = useState<Record<string, GenKind[]>>({})
  const timers = useRef(new Map<string, number>())

  const sourceById = useCallback((id: string) => sources.find(s => s.id === id), [sources])
  const update = useCallback((id: string, change: (source: Source) => Source) =>
    setSources(prev => prev.map(s => (s.id === id ? change(s) : s))), [])

  const prefsOf = useCallback((id: string): SourcePrefs => {
    const source = sourceById(id)
    const fallback: SourcePrefs = source
      ? { scope: initialScope(source), order: defaultOrder(source), count: DEFAULT_COUNT }
      : { scope: '', order: 'useful', count: DEFAULT_COUNT }
    return { ...fallback, ...prefs[id] }
  }, [prefs, sourceById])

  const patchPrefs = useCallback((id: string, patch: Partial<SourcePrefs>) =>
    setPrefs(prev => ({ ...prev, [id]: { ...prefsOf(id), ...patch } })), [prefsOf])

  const decide = useCallback((sourceId: string, cardId: string, status: CardStatus) => update(sourceId, s => ({
    ...s,
    cards: s.cards.map(c => (c.id === cardId ? { ...c, status: c.status === status ? 'pending' : status } : c)),
  })), [update])

  const choosePhrase = useCallback((sourceId: string, cardId: string, sentenceId: string) => update(sourceId, s => ({
    ...s,
    cards: s.cards.map(c => (c.id === cardId ? { ...c, sentenceId } : c)),
  })), [update])

  const take = useCallback((sourceId: string, scope: Scope, count: TakeCount, order: TakeOrder) => {
    setRebuildingIds(prev => new Set(prev).add(sourceId))
    window.setTimeout(() => {
      setSources(prev => prev.map(s => {
        if (s.id !== sourceId) return s
        const n = count === 'all' ? wordsLeft(s, scope) : count
        return { ...s, cards: [...s.cards, ...takeMore(s, scope, n, order)] }
      }))
      setRebuildingIds(prev => {
        const next = new Set(prev)
        next.delete(sourceId)
        return next
      })
    }, REBUILD_MS)
  }, [])

  const setRunning = useCallback((sourceId: string, kind: GenKind, on: boolean) => setRunningKinds(prev => {
    const kinds = (prev[sourceId] ?? []).filter(k => k !== kind)
    return { ...prev, [sourceId]: on ? [...kinds, kind] : kinds }
  }), [])

  const generate = useCallback((sourceId: string, kind: GenKind, mode: GenMode) => {
    const scope = prefsOf(sourceId).scope
    setRunning(sourceId, kind, true)
    const key = `${sourceId}:${kind}`
    window.clearTimeout(timers.current.get(key))
    timers.current.set(key, window.setTimeout(() => {
      timers.current.delete(key)
      update(sourceId, s => {
        const targets = new Set(cardsIn(s, scope).map(c => c.sentenceId))
        return {
          ...s,
          parts: s.parts.map(p => ({
            ...p,
            sentences: p.sentences.map(sentence => (targets.has(sentence.id) && (mode === 'all' || !sentence.polished) ? { ...sentence, polished: true } : sentence)),
          })),
        }
      })
      setRunning(sourceId, kind, false)
    }, GENERATE_MS))
  }, [prefsOf, update, setRunning])

  const cancel = useCallback((sourceId: string, kind: GenKind) => {
    const key = `${sourceId}:${kind}`
    window.clearTimeout(timers.current.get(key))
    timers.current.delete(key)
    setRunning(sourceId, kind, false)
  }, [setRunning])

  const addPart = useCallback((sourceId: string, title: string, text: string) => {
    const source = sourceById(sourceId)
    if (!source) return
    const id = `${sourceId}-p${source.parts.length + 1}`
    const pasted = sentencesFromText(id, text)
    const sentences = pasted.length > 0 ? pasted : buildSentences(id, source.parts.length, BANK_FOR_KIND[source.kind], ADDED_PART_SIZE)
    update(sourceId, s => ({ ...s, parts: [...s.parts, { id, label: title, title, sentences }] }))
    patchPrefs(sourceId, { scope: id })
  }, [sourceById, update, patchPrefs])

  const api = useMemo<PrototypeApi>(() => ({
    sources,
    prefsOf,
    rebuilding: id => rebuildingIds.has(id),
    running: id => runningKinds[id] ?? [],
    setScope: (id, scope) => patchPrefs(id, { scope }),
    setOrder: (id, order) => patchPrefs(id, { order }),
    setCount: (id, count) => patchPrefs(id, { count }),
    decide,
    choosePhrase,
    take,
    generate,
    cancel,
    addPart,
  }), [sources, prefsOf, rebuildingIds, runningKinds, patchPrefs, decide, choosePhrase, take, generate, cancel, addPart])

  return (
    <PrototypeContext.Provider value={api}>
      <Outlet />
    </PrototypeContext.Provider>
  )
}
