// @vitest-environment node
/**
 * Экран ревью показывает то, что прислал сервер, и не считает ни раскладку, ни фокус:
 * каждое изменение идёт через mutate, клиент не отбирает карточки по is_done и разделу,
 * удалённая клиентская логика не возвращается.
 */
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

// Тесты идут из frontends/web.
const REVIEW_DIR = `${ts.sys.getCurrentDirectory()}/src/screens/review`
const CLIENT = `${ts.sys.getCurrentDirectory()}/src/api/client.ts`

const readFile = (path: string): string => {
  const text = ts.sys.readFile(path)
  if (text === undefined) throw new Error(`${path} not found`)
  return text
}

/** Изменения на открытом ревью: каждое отвечает ReviewUpdate и шлётся только через mutate. */
const MUTATIONS = [
  'runReviewGeneration', 'cancelReviewGeneration', 'downloadReviewVideos', 'saveCloze', 'decidePhrase',
  'generateMeaning', 'regeneratePhraseMedia', 'applyTargetImage', 'pasteTargetImage', 'polishPhraseAgain',
  'setPolishReverted', 'editPhrase', 'generatePhraseTTS', 'setPhraseBoundary', 'reportCandidate',
  'replaceWithExample', 'addManualCandidate',
]
const WRAPPER = 'mutate'

/** Клиентская раскладка, фокус и постраничный показ, которые теперь делает сервер. */
const DELETED = [
  'useShownCandidates', 'shownCandidates', 'keepLayout', 'keptLayout', 'focusAfterPress', 'nextFocus',
  'initialFocusId', 'initialFocus', 'FOLDED', 'FOLDED_SECTIONS', 'visibleCandidates', 'listItems', 'ListItem',
  'settle', 'loadCandidates', 'applyReview', 'getReview', 'ReviewDetail', 'initially_shown_candidates',
  'hasCandidateVpnErrors', 'isVpnError', 'isVpnErrorText', 'showMore',
]
const SELECTING = new Set(['filter', 'find', 'findIndex', 'findLast', 'findLastIndex', 'some', 'every'])
const CARD_STATE = new Set(['is_done', 'section'])

const sourceFiles = (): { path: string; text: string }[] =>
  ts.sys.readDirectory(REVIEW_DIR, ['.ts', '.tsx'], undefined, undefined, 1)
    .filter(path => !/\.test\.tsx?$/.test(path))
    .map(path => ({ path: path.slice(REVIEW_DIR.length + 1), text: readFile(path) }))

const parse = (text: string) => ts.createSourceFile('file.tsx', text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

function walk(node: ts.Node, visit: (node: ts.Node) => void): void {
  visit(node)
  node.forEachChild(child => walk(child, visit))
}

const calleeName = (call: ts.CallExpression): string | null => {
  const callee = call.expression
  if (ts.isIdentifier(callee)) return callee.text
  if (ts.isPropertyAccessExpression(callee)) return callee.name.text
  return null
}

const insideWrapper = (node: ts.Node): boolean => {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (ts.isCallExpression(parent) && calleeName(parent) === WRAPPER) return true
  }
  return false
}

/** Вызовы api.<изменение>, которые не стоят внутри mutate(...). */
export function mutationsOutsideWrapper(text: string): string[] {
  const found: string[] = []
  walk(parse(text), node => {
    if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) return
    const { expression: owner, name } = node.expression
    if (ts.isIdentifier(owner) && owner.text === 'api' && MUTATIONS.includes(name.text) && !insideWrapper(node)) found.push(name.text)
  })
  return found
}

/** Отбор (filter, find, some…), чей предикат читает is_done или раздел карточки. */
export function selectionsByCardState(text: string): string[] {
  const found: string[] = []
  walk(parse(text), node => {
    if (!ts.isCallExpression(node) || !SELECTING.has(calleeName(node) ?? '')) return
    const predicate = node.arguments[0]
    if (!predicate || !(ts.isArrowFunction(predicate) || ts.isFunctionExpression(predicate))) return
    walk(predicate.body, inner => {
      if (ts.isPropertyAccessExpression(inner) && CARD_STATE.has(inner.name.text)) found.push(node.getText())
    })
  })
  return found
}

const deletedNamesIn = (text: string): string[] => DELETED.filter(name => new RegExp(`\\b${name}\\b`).test(text))

describe('review screen architecture', () => {
  it('sends every review change through mutate', () => {
    const offences = sourceFiles().flatMap(file => mutationsOutsideWrapper(file.text).map(name => `${file.path}: ${name}`))
    expect(offences).toEqual([])
  })

  it('every listed change takes the review context and answers with the review update', () => {
    const client = readFile(CLIENT)
    for (const name of MUTATIONS) {
      expect(client, name).toMatch(new RegExp(`\\b${name}: \\(ctx: ReviewContext[,)]`))
    }
  })

  it('keeps none of the client layout, focus and paging logic', () => {
    const offences = [...sourceFiles(), { path: 'api/client.ts', text: readFile(CLIENT) }]
      .flatMap(file => deletedNamesIn(file.text).map(name => `${file.path}: ${name}`))
    expect(offences).toEqual([])
    expect(sourceFiles().filter(file => file.text.includes('Show more')).map(file => file.path)).toEqual([])
  })

  it('selects no cards by is_done or section: it shows these values, it does not compute with them', () => {
    const offences = sourceFiles().flatMap(file => selectionsByCardState(file.text).map(code => `${file.path}: ${code}`))
    expect(offences).toEqual([])
  })

  it('catches a planted change outside mutate and a planted selection by card state', () => {
    expect(mutationsOutsideWrapper('const f = () => api.decidePhrase(ctx, 1, "learn")')).toEqual(['decidePhrase'])
    expect(mutationsOutsideWrapper('mutate(ctx => api.decidePhrase(ctx, 1, "learn"))')).toEqual([])
    expect(selectionsByCardState('cards.filter(c => !c.is_done)')).toHaveLength(1)
    expect(selectionsByCardState('rows.some(function (r) { return r.section === s })')).toHaveLength(1)
    expect(selectionsByCardState('rows.find(r => r.index === 1)')).toEqual([])
    expect(deletedNamesIn('const x = keepLayout(a, b)')).toEqual(['keepLayout'])
  })
})
