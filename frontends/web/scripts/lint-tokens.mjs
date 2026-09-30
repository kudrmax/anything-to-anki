// Проверка «никаких хардкодов»: любое визуальное значение живёт только в src/styles/tokens.css.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const TOKENS_FILE = 'styles/tokens.css'

const HEX = /#[0-9a-fA-F]{3,8}\b/
const COLOUR_FUNCTION = /\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(/i
const GRADIENT = /gradient\(/i
const NAMED_COLOUR = /(?<![-\w])(white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|brown|cyan|magenta|silver|gold|navy|teal|olive|maroon|lime|aqua|fuchsia|indigo|violet|beige|ivory|coral|crimson|salmon|tomato|khaki|orchid|plum|tan|turquoise|lavender)(?![-\w])/i
const NUMBER = /(?<![\w-])-?\d*\.?\d+[a-z%]*/gi
// Числа, которые не несут дизайн-решения: ноль, единица, «весь размер», «половина», доли сетки.
const NEUTRAL_NUMBER = /^(0|1|-1|100%|50%|\d+fr)$/i

const CODE_LENGTH = /(?<![\w-])\d*\.?\d+(px|rem|em|vh|vw|dvh|ch|pt)\b/i
const STYLE_OBJECT = /style=\{\{(.*?)\}(?:\s*as\s+CSSProperties)?\}/
const STYLE_KEY = /(['"]?)([\w-]+)\1\s*:/g
const NUMERIC_ATTRIBUTE = /\b(size|width|height|strokeWidth)=\{?["']?\d/
const STYLE_MUTATION = /\.style\.(?!setProperty)/
const TAILWIND = /className="[^"]*\b(flex|grid|p[xytblr]?-\d|m[xytblr]?-\d|gap-\d|text-\[|bg-\[|rounded)/

/** Значения деклараций строки CSS: всё после последней открывающей скобки. */
function cssValues(line) {
  const body = line.includes('{') ? line.slice(line.lastIndexOf('{') + 1) : line
  return body.split(';').map(declaration => declaration.slice(declaration.indexOf(':') + 1)).join(' ')
}

function cssProblems(line) {
  const problems = []
  if (/^\s*@media\b/.test(line)) problems.push('media query (breakpoints live in tokens.css)')
  const values = cssValues(line.replace(/\/\*.*?\*\//g, ''))
  if (HEX.test(values)) problems.push('hex colour')
  if (COLOUR_FUNCTION.test(values)) problems.push('colour function')
  if (GRADIENT.test(values)) problems.push('gradient')
  if (NAMED_COLOUR.test(values)) problems.push('named colour')
  const withoutVars = values.replace(/var\(--[\w-]+\)/g, '')
  for (const number of withoutVars.match(NUMBER) ?? []) {
    if (!NEUTRAL_NUMBER.test(number)) problems.push(`numeric literal ${number}`)
  }
  return problems
}

function codeProblems(line) {
  const problems = []
  if (HEX.test(line)) problems.push('hex colour')
  if (/\b(rgba?|hsla?|oklch|oklab)\(/i.test(line)) problems.push('colour function')
  if (CODE_LENGTH.test(line)) problems.push('length literal')
  if (/style=\{(?!\{)/.test(line)) problems.push('style from a variable (pass CSS custom properties inline)')
  if (/style=\{\{/.test(line)) {
    const object = STYLE_OBJECT.exec(line)
    const keys = object ? [...object[1].matchAll(STYLE_KEY)].map(match => match[2]) : null
    if (!keys || keys.some(key => !key.startsWith('--'))) problems.push('inline style (only CSS custom properties are allowed)')
  }
  if (NUMERIC_ATTRIBUTE.test(line)) problems.push('numeric size attribute')
  if (STYLE_MUTATION.test(line)) problems.push('direct style mutation')
  if (TAILWIND.test(line)) problems.push('Tailwind utility')
  return problems
}

/** Проблемы одного файла: строки вида `путь:строка  что  текст`. */
export function findProblems(rel, content) {
  if (rel === TOKENS_FILE || /\.test\.[cm]?[jt]sx?$/.test(rel)) return []
  const check = rel.endsWith('.css') ? cssProblems : /\.tsx?$/.test(rel) ? codeProblems : null
  if (!check) return []
  return content.split('\n').flatMap((line, i) => check(line).map(what => `${rel}:${i + 1}  ${what}:  ${line.trim()}`))
}

const walk = dir => readdirSync(dir).flatMap(name => {
  const path = join(dir, name)
  return statSync(path).isDirectory() ? walk(path) : [path]
})

function main() {
  const src = fileURLToPath(new URL('../src/', import.meta.url))
  const problems = walk(src).flatMap(path => findProblems(relative(src, path), readFileSync(path, 'utf8')))
  if (problems.length) {
    console.error(problems.join('\n'))
    console.error(`\n${problems.length} hardcoded value(s). Move them to src/${TOKENS_FILE}.`)
    process.exit(1)
  }
  console.log('lint:tokens ok')
}

if (process.argv[1] && import.meta.url.startsWith('file:') && process.argv[1] === fileURLToPath(import.meta.url)) main()
