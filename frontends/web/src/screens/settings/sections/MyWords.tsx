import { useState, type ReactNode } from 'react'
import { X } from 'lucide-react'
import type { KnownWord } from '@/api/types'
import { Button, Empty, Field, IconButton, Tabs, Text } from '@/ui'
import { unknownWordKey, type SettingsStore } from '../useSettings'
import css from '../settings.module.css'

export type WordListKind = 'known' | 'learning' | 'unknown'

const PAGE = 50
const TIMER_KNOWN_LABEL = 'after 30 days in Anki'
const DAY_FORMAT: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, DAY_FORMAT)
const IN_ANKI_LABEL = 'In Anki'
const WAITING_LABEL = 'Waiting for export'
const KNOWN_HINT = "Not suggested in new sources. Remove a word to make it new again everywhere."
const LEARNING_HINT = 'Not suggested as new while you learn them. A word in Anki becomes known on the day shown.'
const UNKNOWN_HINT = "Words you marked with Mark words you don't know (U) on a card. A phrase with one of them besides its target never counts as ready."

interface MyWordsProps {
  store: SettingsStore
  list: WordListKind
  onList: (list: WordListKind) => void
}

export function MyWords({ store, list, onList }: MyWordsProps) {
  const learning = store.learningWords
  return (
    <>
      <Tabs
        value={list}
        options={[
          { value: 'known', label: 'Known', count: store.knownWords.length },
          { value: 'learning', label: 'Learning', count: learning.in_anki.length + learning.awaiting_export.length },
          { value: 'unknown', label: 'Marked unknown', count: store.unknownWords.length },
        ]}
        onChange={onList}
      />
      {list === 'known' && <KnownWords store={store} />}
      {list === 'learning' && <LearningWords store={store} />}
      {list === 'unknown' && <UnknownWords store={store} />}
    </>
  )
}

interface Column {
  title: string
  /** Колонка, которую на узком экране можно убрать. */
  secondary?: boolean
}

interface Row {
  key: string
  word: string
  cells: ReactNode[]
  onRemove?: () => void
}

interface WordTableProps {
  hint: string
  empty: string
  columns: Column[]
  rows: Row[]
  deletingKey?: string | null
}

/** Список слов: поиск, новые сверху, страницами. */
function WordTable({ hint, empty, columns, rows, deletingKey = null }: WordTableProps) {
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)
  if (rows.length === 0) return <Empty>{empty}</Empty>

  const needle = query.trim().toLowerCase()
  const matches = needle ? rows.filter(row => row.word.toLowerCase().includes(needle)) : rows
  const page = matches.slice(0, shown)
  const removable = rows.some(row => row.onRemove)
  const cellClass = (column: Column) => (column.secondary ? `${css.cell} ${css.secondary}` : css.cell)

  return (
    <>
      <p className={css.hint}>{hint}</p>
      <div className={css.wordsBar}>
        <Field type="search" value={query} placeholder={`Search ${rows.length} words`} onChange={e => { setQuery(e.target.value); setShown(PAGE) }} />
      </div>
      {matches.length === 0 ? <Empty>Nothing found.</Empty> : (
        <table className={css.table}>
          <thead>
            <tr>
              <th className={css.cell}>Word</th>
              {columns.map(column => <th key={column.title} className={cellClass(column)}>{column.title}</th>)}
              {removable && <th className={css.action} aria-label="Remove" />}
            </tr>
          </thead>
          <tbody>
            {page.map(row => (
              <tr key={row.key}>
                <td className={`${css.cell} ${css.word}`}>{row.word}</td>
                {row.cells.map((cell, index) => <td key={columns[index].title} className={cellClass(columns[index])}>{cell}</td>)}
                {removable && (
                  <td className={css.action}>
                    {row.onRemove && <IconButton icon={X} label={`Remove ${row.word}`} busy={deletingKey === row.key} onClick={row.onRemove} />}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {matches.length > page.length && (
        <div className={css.more}>
          <Button variant="link" onClick={() => setShown(shown + PAGE)}>Show {Math.min(PAGE, matches.length - page.length)} more</Button>
          <Text tone="muted" size="s">{page.length} of {matches.length}</Text>
        </div>
      )}
    </>
  )
}

function KnownSince({ word }: { word: KnownWord }) {
  return (
    <span className={css.since}>
      {day(word.created_at)}
      {word.by_timer && <Text tone="muted" size="s">{TIMER_KNOWN_LABEL}</Text>}
    </span>
  )
}

export function KnownWords({ store }: { store: SettingsStore }) {
  return (
    <>
      {store.knownError && <Text tone="err">{store.knownError}</Text>}
      <WordTable
        hint={KNOWN_HINT}
        empty="No known words yet. Words you mark Know in review appear here."
        columns={[{ title: 'Part of speech', secondary: true }, { title: 'Known since' }]}
        rows={store.knownWords.map(word => ({
          key: word.removal_key,
          word: word.lemma,
          cells: [
            <Text tone="muted">{word.pos?.toLowerCase() ?? ''}</Text>,
            <KnownSince word={word} />,
          ],
          onRemove: () => void store.deleteWord(word),
        }))}
        deletingKey={store.deletingKey}
      />
    </>
  )
}

/** «Учу» — только для просмотра: в Anki (с днём, когда станет Known) и ждут экспорта. */
export function LearningWords({ store }: { store: SettingsStore }) {
  const { in_anki: inAnki, awaiting_export: awaiting } = store.learningWords
  return (
    <WordTable
      hint={LEARNING_HINT}
      empty="Nothing to learn yet. Mark words as Learn in review."
      columns={[{ title: 'Status' }, { title: 'Known on' }]}
      rows={[
        ...awaiting.map(lemma => ({ key: `waiting:${lemma}`, word: lemma, cells: [<Text tone="muted">{WAITING_LABEL}</Text>, ''] })),
        ...inAnki.map(word => ({ key: `anki:${word.lemma}`, word: word.lemma, cells: [<Text tone="muted">{IN_ANKI_LABEL}</Text>, day(word.known_on)] })),
      ]}
    />
  )
}

export function UnknownWords({ store }: { store: SettingsStore }) {
  return (
    <WordTable
      hint={UNKNOWN_HINT}
      empty="No words yet. Mark them on a card with Mark words you don't know (U)."
      columns={[{ title: 'Added' }]}
      rows={store.unknownWords.map(word => ({
        key: unknownWordKey(word.id),
        word: word.lemma,
        cells: [day(word.created_at)],
        onRemove: () => void store.deleteUnknownWord(word.id),
      }))}
      deletingKey={store.deletingKey}
    />
  )
}
