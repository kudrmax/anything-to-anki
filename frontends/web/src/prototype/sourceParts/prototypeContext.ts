// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { createContext, useContext } from 'react'
import type { CardStatus, Scope, Source, TakeOrder } from './mockData'

export const PROTOTYPE_PATH = '/prototype/source-parts'

export type TakeCount = number | 'all'
export type GenKind = 'polish' | 'meaning' | 'tts'
export type GenMode = 'missing' | 'all'

export interface SourcePrefs {
  scope: Scope
  order: TakeOrder
  count: TakeCount
}

export interface PrototypeApi {
  sources: Source[]
  prefsOf: (sourceId: string) => SourcePrefs
  rebuilding: (sourceId: string) => boolean
  running: (sourceId: string) => GenKind[]
  setScope: (sourceId: string, scope: Scope) => void
  setOrder: (sourceId: string, order: TakeOrder) => void
  setCount: (sourceId: string, count: TakeCount) => void
  decide: (sourceId: string, cardId: string, status: CardStatus) => void
  choosePhrase: (sourceId: string, cardId: string, sentenceId: string) => void
  take: (sourceId: string, scope: Scope, count: TakeCount, order: TakeOrder) => void
  generate: (sourceId: string, kind: GenKind, mode: GenMode) => void
  cancel: (sourceId: string, kind: GenKind) => void
  addPart: (sourceId: string, title: string, text: string) => void
}

export const PrototypeContext = createContext<PrototypeApi | null>(null)

export function usePrototype(): PrototypeApi {
  const api = useContext(PrototypeContext)
  if (!api) throw new Error('usePrototype must be used inside PrototypeProvider')
  return api
}
