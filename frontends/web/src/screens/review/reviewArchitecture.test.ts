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
  // Текст целиком: теперь куски по оглавлению.
  'getReviewDocuments', 'loadDocuments', 'forgetDone', 'listMarkers', 'SourceDocument',
]
/** Чтения текста открытого ревью: только через send, чтобы истёкшее ревью открывалось заново. */
const TEXT_READS = ['reviewText', 'reviewContents']
const SEND = 'send'
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

const insideWrapper = (node: ts.Node, wrapper = WRAPPER): boolean => {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (ts.isCallExpression(parent) && calleeName(parent) === wrapper) return true
  }
  return false
}

/** Обращения к api.<чтение текста> не ради вызова внутри send(...). */
export function textReadsOutsideSend(text: string): string[] {
  const found: string[] = []
  walk(parse(text), node => {
    if (!ts.isPropertyAccessExpression(node) || !isApi(node.expression) || !TEXT_READS.includes(node.name.text)) return
    const called = ts.isCallExpression(node.parent) && node.parent.expression === node
    if (!called || !insideWrapper(node.parent, SEND)) found.push(node.name.text)
  })
  return found
}

/** Вызовы api.<изменение>, которые не стоят внутри mutate(...). */
const isApi = (node: ts.Node): boolean => ts.isIdentifier(node) && node.text === 'api'

/** Имя изменения, если узел — обращение к api.<изменение> или api['<изменение>']. */
function mutationReferenced(node: ts.Node): string | null {
  if (ts.isPropertyAccessExpression(node) && isApi(node.expression)) return MUTATIONS.includes(node.name.text) ? node.name.text : null
  if (ts.isElementAccessExpression(node) && isApi(node.expression)) {
    const key = node.argumentExpression
    // Ключ, вычисленный на ходу, проверить нельзя: такой доступ к api запрещён целиком.
    if (!ts.isStringLiteralLike(key)) return `api[${key.getText()}]`
    return MUTATIONS.includes(key.text) ? key.text : null
  }
  return null
}

/**
 * Изменения, отправленные не через mutate: вызов api.<изменение> вне mutate(...), любое обращение
 * к нему не ради вызова (ссылка, сохранённая в переменную) и деструктуризация из api.
 */
export function mutationsOutsideWrapper(text: string): string[] {
  const found: string[] = []
  walk(parse(text), node => {
    const name = mutationReferenced(node)
    if (name !== null) {
      const called = ts.isCallExpression(node.parent) && node.parent.expression === node
      const computed = name.startsWith('api[')
      if (computed || !called || !insideWrapper(node.parent)) found.push(name)
      return
    }
    if (ts.isVariableDeclaration(node) && node.initializer && isApi(node.initializer) && ts.isObjectBindingPattern(node.name)) {
      for (const element of node.name.elements) {
        const key = (element.propertyName ?? element.name).getText()
        if (MUTATIONS.includes(key)) found.push(key)
      }
    }
  })
  return found
}

/** Читает ли код is_done или раздел карточки: через точку или деструктуризацией. */
function readsCardState(node: ts.Node): boolean {
  let reads = false
  walk(node, inner => {
    if (ts.isPropertyAccessExpression(inner) && CARD_STATE.has(inner.name.text)) reads = true
    if (ts.isElementAccessExpression(inner) && ts.isStringLiteralLike(inner.argumentExpression) && CARD_STATE.has(inner.argumentExpression.text)) reads = true
    if (ts.isBindingElement(inner) && CARD_STATE.has((inner.propertyName ?? inner.name).getText())) reads = true
  })
  return reads
}

const isLoop = (node: ts.Node): node is ts.IterationStatement =>
  ts.isForStatement(node) || ts.isForOfStatement(node) || ts.isForInStatement(node) || ts.isWhileStatement(node) || ts.isDoStatement(node)

/** Отбор карточек по is_done или разделу: предикат filter, find, some… или условие внутри цикла. */
export function selectionsByCardState(text: string): string[] {
  const found: string[] = []
  walk(parse(text), node => {
    if (ts.isCallExpression(node) && SELECTING.has(calleeName(node) ?? '')) {
      const predicate = node.arguments[0]
      if (predicate && (ts.isArrowFunction(predicate) || ts.isFunctionExpression(predicate)) && readsCardState(predicate)) found.push(node.getText())
      return
    }
    if (!isLoop(node)) return
    if (ts.isForOfStatement(node) && ts.isVariableDeclarationList(node.initializer) && readsCardState(node.initializer)) found.push(node.getText())
    walk(node.statement, inner => {
      const condition = ts.isIfStatement(inner) ? inner.expression : ts.isConditionalExpression(inner) ? inner.condition : null
      if (condition && readsCardState(condition)) found.push(inner.getText())
    })
    const loopCondition = ts.isForStatement(node) ? node.condition : ts.isWhileStatement(node) || ts.isDoStatement(node) ? node.expression : undefined
    if (loopCondition && readsCardState(loopCondition)) found.push(node.getText())
  })
  return found
}

const deletedNamesIn = (text: string): string[] => DELETED.filter(name => new RegExp(`\\b${name}\\b`).test(text))

describe('review screen architecture', () => {
  it('sends every review change through mutate', () => {
    const offences = sourceFiles().flatMap(file => mutationsOutsideWrapper(file.text).map(name => `${file.path}: ${name}`))
    expect(offences).toEqual([])
  })

  it('reads the text of the review only through send', () => {
    const offences = sourceFiles().flatMap(file => textReadsOutsideSend(file.text).map(name => `${file.path}: ${name}`))
    expect(offences).toEqual([])
    expect(sourceFiles().some(file => file.text.includes('api.reviewText('))).toBe(true)
    expect(textReadsOutsideSend('const f = () => api.reviewText(ctx, 1, 0)')).toEqual(['reviewText'])
    expect(textReadsOutsideSend('send(ctx => api.reviewContents(ctx))')).toEqual([])
    expect(textReadsOutsideSend('const read = api.reviewContents')).toEqual(['reviewContents'])
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
    expect(mutationsOutsideWrapper('const { decidePhrase } = api')).toEqual(['decidePhrase'])
    expect(mutationsOutsideWrapper('const { decidePhrase: decide } = api')).toEqual(['decidePhrase'])
    expect(mutationsOutsideWrapper('mutate(ctx => api["decidePhrase"](ctx, 1, "learn")); api["editPhrase"](ctx, 1, "p")')).toEqual(['editPhrase'])
    expect(mutationsOutsideWrapper('const send = api.decidePhrase; mutate(ctx => send(ctx, 1, "learn"))')).toEqual(['decidePhrase'])
    expect(mutationsOutsideWrapper('mutate(ctx => api[name](ctx))')).toEqual(['api[name]'])
    expect(selectionsByCardState('cards.filter(({ is_done }) => !is_done)')).toHaveLength(1)
    expect(selectionsByCardState('cards.find(({ section: s }) => s === x)')).toHaveLength(1)
    expect(selectionsByCardState('for (const c of cards) { if (c.is_done) continue; out.push(c) }')).toHaveLength(1)
    expect(selectionsByCardState('for (const { section } of rows) out.push(section)')).toHaveLength(1)
    expect(selectionsByCardState('while (rows[i].section !== s) i++')).toHaveLength(1)
    expect(selectionsByCardState('for (const r of rows) out.push(r.is_done ? 1 : 0)')).toHaveLength(1)
    expect(selectionsByCardState('for (const r of rows) if (r.phrase_id !== null) out.push(r)')).toEqual([])
    expect(selectionsByCardState('cards.filter(c => !c.is_done)')).toHaveLength(1)
    expect(selectionsByCardState('rows.some(function (r) { return r.section === s })')).toHaveLength(1)
    expect(selectionsByCardState('rows.find(r => r.index === 1)')).toEqual([])
    expect(deletedNamesIn('const x = keepLayout(a, b)')).toEqual(['keepLayout'])
  })
})
