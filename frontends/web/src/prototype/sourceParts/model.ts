// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import type { TakeCount } from './prototypeContext'
import { newCard, WHOLE, type Card, type Part, type Scope, type Sentence, type Source, type TakeOrder } from './mockData'

export const partsIn = (source: Source, scope: Scope): Part[] =>
  scope === WHOLE ? source.parts : source.parts.filter(p => p.id === scope)

export const cardsIn = (source: Source, scope: Scope): Card[] =>
  scope === WHOLE ? source.cards : source.cards.filter(c => c.partId === scope)

export const scopeLabel = (source: Source, scope: Scope): string =>
  scope === WHOLE ? source.wholeLabel : source.parts.find(p => p.id === scope)?.label ?? ''

export function sentenceIndex(source: Source): Map<string, Sentence> {
  return new Map(source.parts.flatMap(p => p.sentences).map(s => [s.id, s]))
}

export interface Progress {
  decided: number
  total: number
}

export function readyProgress(cards: Card[]): Progress {
  const ready = cards.filter(c => c.section === 'ready')
  return { decided: ready.filter(c => c.status !== 'pending').length, total: ready.length }
}

export function defaultOrder(source: Source): TakeOrder {
  if (source.kind === 'book') return 'useful'
  if (source.kind === 'text' && source.hasHeadings) return 'useful'
  return 'text'
}

/** First phrase of every word that can still be taken in the scope: not decided anywhere and without a card here. */
function eligible(source: Source, scope: Scope): Sentence[] {
  const decided = new Set(source.cards.filter(c => c.status !== 'pending').map(c => c.lemma))
  const carded = new Set(cardsIn(source, scope).map(c => c.lemma))
  const seen = new Set<string>()
  const result: Sentence[] = []
  for (const s of partsIn(source, scope).flatMap(p => p.sentences)) {
    if (decided.has(s.lemma) || carded.has(s.lemma) || seen.has(s.lemma)) continue
    seen.add(s.lemma)
    result.push(s)
  }
  return result
}

export const wordsLeft = (source: Source, scope: Scope): number => eligible(source, scope).length

/** Text order continues right after the last phrase that already became a card. */
function inTextOrder(source: Source, scope: Scope, candidates: Sentence[]): Sentence[] {
  const sequence = partsIn(source, scope).flatMap(p => p.sentences)
  const position = new Map(sequence.map((s, i) => [s.id, i]))
  const cardSentences = new Set(cardsIn(source, scope).map(c => c.sentenceId))
  const last = sequence.reduce((max, s, i) => (cardSentences.has(s.id) ? i : max), -1)
  const rank = (s: Sentence) => {
    const p = position.get(s.id) ?? 0
    return p > last ? p - last : p + sequence.length
  }
  return [...candidates].sort((a, b) => rank(a) - rank(b))
}

function ordered(source: Source, scope: Scope, order: TakeOrder): Sentence[] {
  const candidates = eligible(source, scope)
  if (order === 'text') return inTextOrder(source, scope, candidates)
  if (order === 'useful') return [...candidates].sort((a, b) => b.useful - a.useful)
  return [...candidates].sort((a, b) => b.key - a.key)
}

/** Best phrase of a word in the scope: one that already has Polish, otherwise the first. */
function bestPhrase(source: Source, scope: Scope, lemma: string, fallback: Sentence): Sentence {
  const all = partsIn(source, scope).flatMap(p => p.sentences).filter(s => s.lemma === lemma)
  return all.find(s => s.polished) ?? fallback
}

export function takeMore(source: Source, scope: Scope, count: number, order: TakeOrder): Card[] {
  return ordered(source, scope, order).slice(0, count).map((s, i) =>
    newCard(source.id, source.cards.length + i, bestPhrase(source, scope, s.lemma, s)))
}

export function occurrences(source: Source, scope: Scope, lemma: string): Sentence[] {
  return partsIn(source, scope).flatMap(p => p.sentences).filter(s => s.lemma === lemma)
}

/** Phrase split around its target: before, target, after. */
export function phraseParts(s: Sentence): [string, string, string] {
  const at = s.text.toLowerCase().indexOf(s.target.toLowerCase())
  if (at < 0) return [s.text, '', '']
  return [s.text.slice(0, at), s.text.slice(at, at + s.target.length), s.text.slice(at + s.target.length)]
}

const SNIPPET_LENGTH = 64

export const snippet = (text: string): string =>
  text.length > SNIPPET_LENGTH ? `${text.slice(0, SNIPPET_LENGTH - 1)}…` : text

export function takeLabel(from: string, left: number, count: TakeCount): string {
  const where = from ? ` from ${from}` : ''
  if (count === 'all' || count >= left) return `All ${left}${where}`
  return `${count} more${where} · ~${left} left`
}
