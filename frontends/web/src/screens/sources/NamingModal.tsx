import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from 'react'
import { ArrowRight, Undo2 } from 'lucide-react'
import { api } from '@/api/client'
import type { CollectionChoice, CollectionNode, CollectionTree, Naming, NamingRequired } from '@/api/types'
import { messageOf } from '@/lib/apiError'
import { Button, Field, Icon, Label, Modal, Text } from '@/ui'
import { RuleField } from './RuleField'
import css from './NamingModal.module.css'

interface NamingModalProps {
  required: NamingRequired
  tree: CollectionTree | null
  onCancel: () => void
  onConfirm: (naming: Naming) => void
}

const RENDER_DELAY_MS = 300
const NO_COLLECTION = 'No collection'
const PATH_JOINER = ' / '

interface Existing {
  id: number
  name: string
  path: string[]
}

function flatten(nodes: CollectionNode[], path: string[] = []): Existing[] {
  return nodes.flatMap(node => [{ id: node.id, name: node.name, path }, ...flatten(node.children, [...path, node.name])])
}

/** Коллекция с набранным именем: сперва верхнего уровня, иначе единственная вложенная с таким именем. */
function sameNamed(existing: Existing[], typed: string): Existing | undefined {
  const named = existing.filter(e => e.name.toLowerCase() === typed.toLowerCase())
  return named.find(e => e.path.length === 0) ?? (named.length === 1 ? named[0] : undefined)
}

/** Окно названий: коллекция и правило для всех источников одного добавления, строку можно переписать руками. */
export function NamingModal({ required, tree, onCancel, onConfirm }: NamingModalProps) {
  const existing = flatten(tree?.collections ?? [])
  const nameOf = (choice: CollectionChoice | null): string | null =>
    choice?.new_name ?? existing.find(e => e.id === choice?.existing_id)?.name ?? null

  const [collection, setCollection] = useState<CollectionChoice | null>(required.default_collection)
  const [search, setSearch] = useState(() => nameOf(required.default_collection) ?? '')
  const [picking, setPicking] = useState(false)
  const [rule, setRule] = useState(required.default_rule)
  const [rendered, setRendered] = useState<string[]>([])
  const [ruleError, setRuleError] = useState<string | null>(null)
  // Для какого правила и коллекции пришёл последний ответ: пока не для текущих — проверка идёт.
  const [checkedFor, setCheckedFor] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<number, string>>({})
  const collectionName = nameOf(collection)
  const checkKey = `${rule}\n${collectionName ?? ''}`
  const checking = checkedFor !== checkKey

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api.renderNames(rule, collectionName, required.items.map(item => item.own_title), controller.signal)
        .then(names => { setRendered(names); setRuleError(null); setCheckedFor(checkKey) })
        .catch(e => { if (!controller.signal.aborted) { setRuleError(messageOf(e)); setCheckedFor(checkKey) } })
    }, RENDER_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [rule, collectionName, checkKey, required.items])

  const listRef = useRef<HTMLDivElement>(null)
  const query = search.trim().toLowerCase()
  const matches = existing.filter(e => e.name.toLowerCase().includes(query))
  const canCreate = query !== '' && !sameNamed(existing, search.trim())

  const pick = (choice: CollectionChoice | null) => {
    setCollection(choice)
    setSearch(nameOf(choice) ?? (choice?.new_name ?? ''))
    setPicking(false)
  }

  /** Набранное без выбора из списка: пусто — без коллекции, имя существующей — она, иначе новая. */
  const type = (value: string) => {
    setSearch(value)
    setPicking(true)
    const typed = value.trim()
    const same = sameNamed(existing, typed)
    setCollection(!typed ? null : same ? { existing_id: same.id, new_name: null } : { existing_id: null, new_name: typed })
  }

  const closeOnBlur = (e: FocusEvent) => {
    if (!listRef.current?.contains(e.relatedTarget as Node | null)) setPicking(false)
  }

  const closeOnEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && picking) {
      e.stopPropagation()
      setPicking(false)
    }
  }

  const backToRule = (index: number) =>
    setEdits(prev => Object.fromEntries(Object.entries(prev).filter(([row]) => Number(row) !== index)))

  const confirm = () => onConfirm({
    collection,
    rule,
    titles: Object.fromEntries(Object.entries(edits).filter(([, title]) => title.trim() !== '')),
  })

  return (
    <Modal
      title={required.heading}
      wide
      onClose={onCancel}
      footer={
        <>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          <Button variant="fill" disabled={checking || ruleError !== null} onClick={confirm}>Add</Button>
        </>
      }
    >
      <div className={css.section}>
        <Label flush>Collection</Label>
        <Field
          role="combobox"
          aria-expanded={picking}
          placeholder={NO_COLLECTION}
          value={search}
          onFocus={() => setPicking(true)}
          onBlur={closeOnBlur}
          onKeyDown={closeOnEscape}
          onChange={e => type(e.target.value)}
        />
        {picking && (
          // Нажатие на вариант не уводит фокус из поля: иначе WebKit закрывает список раньше клика.
          <div ref={listRef} className={css.options} role="listbox" aria-label="Collection" onMouseDown={e => e.preventDefault()}>
            <button type="button" role="option" aria-selected={collection === null} className={css.option} onClick={() => pick(null)}>{NO_COLLECTION}</button>
            {matches.map(e => (
              <button key={e.id} type="button" role="option" aria-selected={collection?.existing_id === e.id} className={css.option} onClick={() => pick({ existing_id: e.id, new_name: null })}>
                {e.path.length > 0 && <span className={css.parent}>{e.path.join(PATH_JOINER)}{PATH_JOINER}</span>}
                {e.name}
              </button>
            ))}
            {canCreate && (
              <button type="button" role="option" aria-selected={false} className={css.option} onClick={() => pick({ existing_id: null, new_name: search.trim() })}>
                Create «{search.trim()}»
              </button>
            )}
          </div>
        )}
      </div>
      <div className={css.section}>
        <Label flush>Name them</Label>
        <RuleField value={rule} variables={required.variables} onChange={setRule} />
        {ruleError && <Text tone="err" size="s">{ruleError}</Text>}
      </div>
      <div className={css.rows}>
        {required.items.map((item, index) => {
          const edited = index in edits
          return (
            <div key={index} className={css.row} data-row>
              <span className={css.label} title={item.label}>{item.label}</span>
              <span className={css.arrow}><Icon as={ArrowRight} size="s" /></span>
              <input
                className={css.title}
                value={edits[index] ?? rendered[index] ?? ''}
                aria-label={`Title of ${item.label}`}
                onChange={e => setEdits(prev => ({ ...prev, [index]: e.target.value }))}
                onBlur={() => { if (edits[index]?.trim() === '') backToRule(index) }}
              />
              {edited ? (
                <button type="button" className={css.reset} aria-label="Back to the rule" onClick={() => backToRule(index)}>
                  <Icon as={Undo2} size="s" />
                </button>
              ) : <span />}
            </div>
          )
        })}
      </div>
    </Modal>
  )
}
