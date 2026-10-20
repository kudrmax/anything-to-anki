import { Fragment } from 'react'
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

/** Правило как текст между плашками: перед, между и после плашек всегда есть поле для текста. */
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

/** Правило названий: переменные — плашками, вставляются кнопками; скобки руками не пишутся. */
export function RuleField({ value, variables, onChange }: RuleFieldProps) {
  const parts = partsOf(value, variables)
  const replaced = (index: number, part: Part | null) =>
    ruleOf(parts.flatMap((p, i) => (i !== index ? [p] : part ? [part] : [])))

  return (
    <div className={css.rule}>
      <div className={css.field}>
        {parts.map((part, index) => (
          <Fragment key={index}>
            {'text' in part ? (
              <input
                className={css.text}
                value={part.text}
                size={Math.max(part.text.length, 1)}
                aria-label="Title text"
                onChange={e => onChange(replaced(index, { text: e.target.value }))}
              />
            ) : (
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
          <Chip key={variable.token} small onClick={() => onChange(value + variable.token)}>+ {variable.label}</Chip>
        ))}
      </div>
    </div>
  )
}
