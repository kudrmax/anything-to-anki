import { Fragment, useState } from 'react'
import { X } from 'lucide-react'
import type { NamingVariable } from '@/api/types'
import { Chip, Icon } from '@/ui'
import css from './RuleField.module.css'

interface RuleFieldProps {
  value: string
  variables: NamingVariable[]
  onChange: (rule: string) => void
}

type Part = { text: string } | { variable: NamingVariable }

const VISIBLE_SPACE = '·'

/** Правило как текст между плашками: перед, между и после плашек всегда есть место для текста. */
function partsOf(rule: string, variables: NamingVariable[]): Part[] {
  const parts: Part[] = []
  let text = ''
  for (let i = 0; i < rule.length;) {
    const variable = variables.find(v => rule.startsWith(v.token, i))
    if (variable) {
      parts.push({ text }, { variable })
      text = ''
      i += variable.token.length
    } else {
      text += rule[i]
      i += 1
    }
  }
  parts.push({ text })
  return parts
}

const ruleOf = (parts: Part[]): string => parts.map(part => ('text' in part ? part.text : part.variable.token)).join('')

/** Новая переменная встаёт в конец через пробел, чтобы не слиться с предыдущим словом. */
const appended = (rule: string, token: string): string => (rule === '' || rule.endsWith(' ') ? rule + token : `${rule} ${token}`)

/** Свой текст: пробелы видны точками, иначе их число не понять. */
function shown(text: string) {
  return [...text].map((char, i) => (char === ' ' ? <span key={i} className={css.space}>{VISIBLE_SPACE}</span> : char))
}

/** Правило названий: переменные и свой текст — плашками; переменные вставляются кнопками, скобки руками не пишутся. */
export function RuleField({ value, variables, onChange }: RuleFieldProps) {
  const [editing, setEditing] = useState<number | null>(null)
  const parts = partsOf(value, variables)
  const replaced = (index: number, part: Part | null) =>
    ruleOf(parts.flatMap((p, i) => (i !== index ? [p] : part ? [part] : [])))

  const renderText = (text: string, index: number) => {
    if (editing === index) {
      return (
        <span className={css.sizer} data-value={text}>
          <input
            autoFocus
            className={css.input}
            value={text}
            aria-label="Title text"
            onChange={e => onChange(replaced(index, { text: e.target.value }))}
            onBlur={() => setEditing(null)}
          />
        </span>
      )
    }
    if (text === '') {
      return <span className={css.slot} data-slot onClick={() => setEditing(index)} />
    }
    return (
      <span className={css.text} data-text role="button" tabIndex={0} onClick={() => setEditing(index)} onFocus={() => setEditing(index)}>
        {shown(text)}
      </span>
    )
  }

  return (
    <div className={css.rule}>
      <div className={css.field} data-rule-field onClick={e => { if (e.target === e.currentTarget) setEditing(parts.length - 1) }}>
        {parts.map((part, index) => (
          <Fragment key={index}>
            {'text' in part ? renderText(part.text, index) : (
              <span className={css.token} data-token={part.variable.token}>
                {part.variable.label}
                <button type="button" className={css.remove} aria-label={`Remove ${part.variable.label}`} onClick={() => onChange(replaced(index, null))}>
                  <Icon as={X} size="s" />
                </button>
              </span>
            )}
          </Fragment>
        ))}
      </div>
      <div className={css.add}>
        {variables.map(variable => (
          <Chip key={variable.token} small onClick={() => onChange(appended(value, variable.token))}>+ {variable.label}</Chip>
        ))}
      </div>
    </div>
  )
}
