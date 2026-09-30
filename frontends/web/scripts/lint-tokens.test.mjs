import { describe, expect, it } from 'vitest'
import { findProblems } from './lint-tokens.mjs'

const css = line => findProblems('ui/X.module.css', line)
const tsx = line => findProblems('ui/X.tsx', line)

describe('lint-tokens: css', () => {
  it('accepts values built only from tokens and neutral keywords', () => {
    expect(css('.a { inset: 0; flex: 1 1 auto; width: 100%; border-radius: 50%; grid-template-columns: 1fr 1fr; margin: calc(var(--s3) * -1); color: var(--tx); transition: opacity var(--t); opacity: 0; }')).toEqual([])
  })
  it.each([
    ['hex colour', '.a { color: #fff; }'],
    ['named colour', '.a { color: red; }'],
    ['modern colour function', '.a { color: oklch(70% 0.1 200); }'],
    ['colour mixed in place', '.a { background: color-mix(in srgb, var(--warn) 14%, transparent); }'],
    ['gradient built in place', '.a { background: linear-gradient(transparent, var(--bg)); }'],
    ['pixel length', '.a { padding: 4px; }'],
    ['uppercase unit', '.a { padding: 4PX; }'],
    ['percentage size', '.a { width: 40%; }'],
    ['viewport unit', '.a { height: 80vh; }'],
    ['unitless font weight', '.a { font-weight: 600; }'],
    ['unitless opacity', '.a { opacity: .5; }'],
    ['unitless z-index', '.a { z-index: 20; }'],
    ['size multiplier', '.a { width: calc(var(--h) * 7); }'],
    ['media query, even on one line', '@media (max-width: 900px) { .a { padding: var(--s1); } }'],
  ])('rejects %s', (_, line) => {
    expect(css(line).length).toBeGreaterThan(0)
  })
})

describe('lint-tokens: tsx', () => {
  it('accepts a style that only passes custom properties', () => {
    expect(tsx("<div style={{ '--p': percent } as CSSProperties} />")).toEqual([])
  })
  it.each([
    ['style object variable', '<div style={style} />'],
    ['style mixing a custom property with a real one', "<div style={{ '--x': x, color: tone }} />"],
    ['numeric size attribute', '<img width={160} />'],
    ['numeric stroke width', '<Icon strokeWidth={2} />'],
    ['direct style mutation', 'el.style.color = tone'],
    ['hex colour in code', "const c = '#ff0000'"],
    ['pixel literal in code', "const w = '12px'"],
  ])('rejects %s', (_, line) => {
    expect(tsx(line).length).toBeGreaterThan(0)
  })
})
