// @vitest-environment node
/**
 * Веб-половина охраны модели статусов (backend: backend/tests/unit/test_architecture_status_model.py).
 *
 * Сравнить значение карточки — выбор, статус, раздел, команду кнопки и т. п. — с конкретным значением
 * значит завести во фронте правило. Это запрещено. Рендерить можно: значение → подпись или тон по таблице,
 * группировка и поиск по значению из переменной, проверка, прислал ли backend значение (`=== null`).
 * Какое значение — карточки, охрана узнаёт по типам TypeScript, а не по имени переменной.
 */
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Типы, значения которых — модель статусов карточки. */
const CARD_TYPES = [
  'CardChoice', 'CandidateSection', 'DecisionButton', 'ButtonCommand', 'Refusal', 'CardNote',
  'ShownStatus', 'ShownWhere', 'ShownTone',
] as const
/** Интерфейсы карточки: их поля — значения карточки, каким бы ни был тип поля. */
const CARD_INTERFACES = new Set(['StoredCandidate', 'Shown', 'CardButton', 'CardState'])
/** Поля этих интерфейсов, которые держат модель (у карточки есть и чужие статусы, например polish_status). */
const CARD_FIELDS = new Set(['choice', 'section', 'status', 'where', 'tone', 'command', 'refused', 'note', 'button'])
const EQUALITY = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
])
const MEMBERSHIP = new Set(['includes', 'has', 'indexOf'])

interface Offence { file: string; line: number; code: string }

const literalsOf = (type: ts.Type): string[] | null => {
  const members = type.isUnion() ? type.types : [type]
  return members.every(m => m.isStringLiteral()) ? members.map(m => (m as ts.StringLiteralType).value).sort() : null
}

function cardTypeSets(checker: ts.TypeChecker, files: readonly ts.SourceFile[]): string[] {
  const sets: string[] = []
  for (const file of files) {
    ts.forEachChild(file, node => {
      if (ts.isTypeAliasDeclaration(node) && (CARD_TYPES as readonly string[]).includes(node.name.text)) {
        const literals = literalsOf(checker.getTypeAtLocation(node.name))
        if (literals) sets.push(literals.join('|'))
      }
    })
  }
  return sets
}

function findOffences(program: ts.Program, isScanned: (file: ts.SourceFile) => boolean): Offence[] {
  const checker = program.getTypeChecker()
  const files = program.getSourceFiles().filter(f => !f.isDeclarationFile)
  const cardSets = new Set(cardTypeSets(checker, files))
  const offences: Offence[] = []

  const unwrap = (node: ts.Expression): ts.Expression =>
    ts.isParenthesizedExpression(node) || ts.isNonNullExpression(node) ? unwrap(node.expression) : node

  const isCardField = (node: ts.Expression): boolean => {
    if (!ts.isPropertyAccessExpression(node) || !CARD_FIELDS.has(node.name.text)) return false
    return (checker.getSymbolAtLocation(node.name)?.declarations ?? []).some(d =>
      ts.isInterfaceDeclaration(d.parent) && CARD_INTERFACES.has(d.parent.name.text))
  }

  const isCardValue = (raw: ts.Expression): boolean => {
    const node = unwrap(raw)
    if (isCardField(node)) return true
    const type = checker.getNonNullableType(checker.getTypeAtLocation(node))
    if (type.aliasSymbol && (CARD_TYPES as readonly string[]).includes(type.aliasSymbol.name)) return true
    const literals = literalsOf(type)
    return literals !== null && literals.length > 1 && cardSets.has(literals.join('|'))
  }

  const isOneValue = (node: ts.Expression): boolean => checker.getTypeAtLocation(unwrap(node)).isStringLiteral()

  const isLiteralList = (node: ts.Expression): boolean => {
    const receiver = unwrap(node)
    if (ts.isArrayLiteralExpression(receiver)) return true
    return ts.isNewExpression(receiver) && (receiver.arguments ?? []).some(a => ts.isArrayLiteralExpression(unwrap(a)))
  }

  const report = (file: ts.SourceFile, node: ts.Node) => {
    const { line } = file.getLineAndCharacterOfPosition(node.getStart(file))
    offences.push({ file: file.fileName, line: line + 1, code: node.getText(file).slice(0, 120) })
  }

  for (const file of files.filter(isScanned)) {
    const visit = (node: ts.Node): void => {
      if (ts.isBinaryExpression(node) && EQUALITY.has(node.operatorToken.kind)) {
        const [left, right] = [node.left, node.right]
        if ((isCardValue(left) && isOneValue(right)) || (isCardValue(right) && isOneValue(left))) report(file, node)
      }
      if (ts.isSwitchStatement(node) && isCardValue(node.expression)) report(file, node.expression)
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
        && MEMBERSHIP.has(node.expression.name.text) && isLiteralList(node.expression.expression)
        && node.arguments.some(isCardValue)) report(file, node)
      ts.forEachChild(node, visit)
    }
    visit(file)
  }
  return offences
}

const isAppSource = (file: ts.SourceFile): boolean =>
  /\/src\//.test(file.fileName) && !/\.test\.tsx?$/.test(file.fileName) && !/reviewFixtures\.ts$/.test(file.fileName)

function appProgram(): ts.Program {
  const configPath = ts.findConfigFile(ts.sys.getCurrentDirectory(), ts.sys.fileExists, 'tsconfig.app.json')
  if (!configPath) throw new Error('tsconfig.app.json not found')
  const config = ts.getParsedCommandLineOfConfigFile(configPath, {}, { ...ts.sys, onUnRecoverableConfigFileDiagnostic: () => {} })
  if (!config) throw new Error('tsconfig.app.json does not parse')
  return ts.createProgram(config.fileNames, config.options)
}

/** Программа из двух файлов в памяти: типы карточки и проверяемый фрагмент. */
function sampleProgram(code: string): ts.Program {
  const types = `
    export type CardChoice = 'none' | 'learn' | 'cloze' | 'known' | 'skip'
    export type CandidateSection = 'ready' | 'extra' | 'probably_known' | 'reviewed'
    export type ButtonCommand = 'decide' | 'edit_cloze'
    export type ShownStatus = 'new' | 'learn' | 'learning' | 'known'
    export type ShownTone = 'open' | 'learning' | 'settled'
    export interface Shown { status: ShownStatus; skipped: boolean; tone: ShownTone }
    export interface CardButton { command: ButtonCommand | null }
    export interface StoredCandidate { choice: CardChoice; section: CandidateSection | null; shown: Shown }
    export interface Source { status: string }
  `
  const files: Record<string, string> = { '/v/types.ts': types, '/v/sample.ts': `import type * as T from './types'\n${code}` }
  const options: ts.CompilerOptions = { strict: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler, types: [], lib: ['lib.es2023.d.ts'] }
  const host = ts.createCompilerHost(options)
  const { getSourceFile, fileExists, readFile } = host
  host.getSourceFile = (name, version, ...rest) =>
    files[name] !== undefined ? ts.createSourceFile(name, files[name], version) : getSourceFile(name, version, ...rest)
  host.fileExists = name => files[name] !== undefined || fileExists(name)
  host.readFile = name => files[name] ?? readFile(name)
  const { directoryExists } = host
  host.directoryExists = dir => dir === '/v' || (directoryExists?.(dir) ?? false)
  return ts.createProgram(Object.keys(files), options, host)
}

const sampleOffences = (code: string) =>
  findOffences(sampleProgram(code), file => file.fileName === '/v/sample.ts').map(o => o.code)

describe('status model guard (web)', () => {
  it('finds no rule over card values in the app', () => {
    const offences = findOffences(appProgram(), isAppSource)
      .map(o => `${o.file.replace(/^.*\/src\//, 'src/')}:${o.line}: ${o.code}`)
    expect(offences).toEqual([])
  }, 30_000)

  it.each([
    ['declare const c: T.StoredCandidate; const r = c.section === \'ready\''],
    ['declare const c: T.StoredCandidate; const r = c.shown.status !== \'new\''],
    ['declare const c: T.StoredCandidate; const r = \'skip\' === c.choice'],
    ['declare const b: T.CardButton; const r = b.command === \'edit_cloze\''],
    ['declare const s: T.Shown; const { status } = s; const r = status === \'new\''],
    ['const NEW = \'new\'; declare const s: T.Shown; const r = s.status === NEW'],
    ['declare const s: T.Shown; const r = s.tone === \'settled\''],
    ['declare const c: T.StoredCandidate; switch (c.choice) { default: }'],
    ['declare const c: T.StoredCandidate; const r = [\'learn\', \'known\'].includes(c.shown.status)'],
    ['declare const c: T.StoredCandidate; const r = new Set([\'extra\']).has(c.section!)'],
    ['declare const x: T.ShownStatus; const r = x === \'known\''],
  ])('catches %s', code => {
    expect(sampleOffences(code)).toHaveLength(1)
  })

  it.each([
    ['declare const c: T.StoredCandidate; const TONE: Record<T.ShownTone, string> = { open: \'a\', learning: \'b\', settled: \'c\' }; const r = TONE[c.shown.tone]'],
    ['declare const b: T.CardButton; const r = b.command === null'],
    ['declare const c: T.StoredCandidate; declare const s: T.CandidateSection | null; const r = c.section === s'],
    ['declare const src: T.Source; const r = src.status === \'reviewed\''],
    ['declare const c: T.StoredCandidate; const r = c.shown.skipped === true'],
    ['declare const open: Set<T.CandidateSection>; declare const c: T.StoredCandidate; const r = open.has(c.section!)'],
  ])('lets through %s', code => {
    expect(sampleOffences(code)).toEqual([])
  })
})
