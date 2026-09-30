import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const TOKENS_FILE = 'styles/tokens.css'
const LEGACY = readFileSync(new URL('./token-lint-legacy.txt', import.meta.url), 'utf8')
  .split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('#'))

const RULES = [
  [/#[0-9a-fA-F]{3,8}\b/, 'hex colour'],
  [/\b(rgba?|hsla?)\(/, 'colour function'],
  [/(?<![\w-])\d*\.?\d+(px|rem|em)\b/, 'length literal'],
  [/style=\{\{(?![^}]*--)/, 'inline style (only CSS custom properties are allowed)'],
  [/\bsize=\{\d/, 'numeric icon size'],
  [/className="[^"]*\b(flex|grid|p[xytblr]?-\d|m[xytblr]?-\d|gap-\d|text-\[|bg-\[|rounded)/, 'Tailwind utility'],
]

const walk = dir => readdirSync(dir).flatMap(name => {
  const path = join(dir, name)
  return statSync(path).isDirectory() ? walk(path) : [path]
})

const problems = []
for (const path of walk(SRC)) {
  const rel = relative(SRC, path)
  if (!/\.(css|tsx?)$/.test(rel) || /\.test\.tsx?$/.test(rel) || rel === TOKENS_FILE) continue
  if (LEGACY.some(prefix => rel === prefix || rel.startsWith(prefix))) continue
  readFileSync(path, 'utf8').split('\n').forEach((line, i) => {
    if (line.trimStart().startsWith('@media')) return
    for (const [re, what] of RULES) if (re.test(line)) problems.push(`${rel}:${i + 1}  ${what}:  ${line.trim()}`)
  })
}

if (problems.length) {
  console.error(problems.join('\n'))
  console.error(`\n${problems.length} hardcoded value(s). Move them to src/${TOKENS_FILE}.`)
  process.exit(1)
}
console.log('lint:tokens ok')
