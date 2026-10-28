import { useState } from 'react'
import type { KnownWord } from '@/api/types'
import { formatDay } from '@/lib/text/format'
import { Button, Empty, Field, RemovableChip, Tabs, Text } from '@/ui'
import { unknownWordKey, type SettingsStore } from '../useSettings'
import css from '../settings.module.css'
import { Group } from './Group'

export type WordListKind = 'known' | 'learning' | 'unknown'

const WORDS_PREVIEW = 60
/** Пометка слова Known по 30 дням в Anki в списке Known. */
const TIMER_KNOWN_LABEL = '30 days in Anki'
const KNOWN_ON_LABEL = 'known on'
const KNOWN_WORDS_HINT = "Known words won't be suggested when processing new sources."
const UNKNOWN_WORDS_HINT = 'Phrases with these words never count as ready: only their target should be new.'
const LEARNING_HINT = 'Words you are learning. A word in Anki becomes known on the day shown; until then they are not suggested as new.'

interface WordListsProps {
  store: SettingsStore
  list: WordListKind
  onList: (list: WordListKind) => void
}

export function WordLists({ store, list, onList }: WordListsProps) {
  const learningCount = store.learningWords.in_anki.length + store.learningWords.awaiting_export.length
  return (
    <>
      <Tabs
        value={list}
        options={[
          { value: 'known', label: 'Known', count: store.knownWords.length },
          { value: 'learning', label: 'Learning', count: learningCount },
          { value: 'unknown', label: 'Unknown', count: store.unknownWords.length },
        ]}
        onChange={onList}
      />
      {list === 'known' && <KnownWords store={store} />}
      {list === 'learning' && <LearningWordsList store={store} />}
      {list === 'unknown' && <UnknownWords store={store} />}
    </>
  )
}

interface ListedWord {
  key: string
  label: string
  details: string[]
  onRemove: () => void
}

interface WordListProps {
  words: ListedWord[]
  hint: string
  empty: string
  deletingKey: string | null
}

function WordList({ words, hint, empty, deletingKey }: WordListProps) {
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(false)
  if (words.length === 0) return <Empty>{empty}</Empty>

  const needle = query.trim().toLowerCase()
  const matches = needle ? words.filter(word => word.label.toLowerCase().includes(needle)) : words
  const shown = showAll || needle ? matches : matches.slice(0, WORDS_PREVIEW)
  const hidden = matches.length - shown.length

  return (
    <>
      <p className={css.hint}>{hint}</p>
      <div className={css.wordsBar}>
        <Field value={query} placeholder={`Search ${words.length} words…`} onChange={e => setQuery(e.target.value)} />
      </div>
      {matches.length === 0 ? <Empty>Nothing found.</Empty> : (
        <div className={css.words}>
          {shown.map(word => (
            <RemovableChip
              key={word.key}
              label={word.label}
              details={word.details}
              disabled={deletingKey === word.key}
              onRemove={word.onRemove}
            />
          ))}
        </div>
      )}
      {hidden > 0 && (
        <div className={css.more}>
          <Button variant="link" onClick={() => setShowAll(true)}>Show all {matches.length}</Button>
        </div>
      )}
    </>
  )
}

const knownWordDetails = (word: KnownWord): string[] =>
  [word.pos?.toLowerCase(), word.by_timer ? TIMER_KNOWN_LABEL : null].filter((detail): detail is string => Boolean(detail))

export function KnownWords({ store }: { store: SettingsStore }) {
  return (
    <>
      {store.knownError && <Text tone="err">{store.knownError}</Text>}
      <WordList
        words={store.knownWords.map(word => ({
          key: word.removal_key,
          label: word.lemma,
          details: knownWordDetails(word),
          onRemove: () => void store.deleteWord(word),
        }))}
        hint={KNOWN_WORDS_HINT}
        empty={`No known words yet. ${KNOWN_WORDS_HINT}`}
        deletingKey={store.deletingKey}
      />
    </>
  )
}

/** «Учу» — только для просмотра: в Anki (с днём, когда станет Known) и ждут экспорта. */
export function LearningWordsList({ store }: { store: SettingsStore }) {
  const { in_anki: inAnki, awaiting_export: awaiting } = store.learningWords
  if (inAnki.length === 0 && awaiting.length === 0) return <Empty>Nothing to learn yet. Mark words as Learn in review.</Empty>
  const groups = [
    { title: 'In Anki', words: inAnki.map(word => ({ lemma: word.lemma, detail: `${KNOWN_ON_LABEL} ${formatDay(word.known_on)}` })) },
    { title: 'Waiting for export', words: awaiting.map(lemma => ({ lemma, detail: null })) },
  ].filter(group => group.words.length > 0)
  return (
    <>
      <p className={css.hint}>{LEARNING_HINT}</p>
      {groups.map(group => (
        <Group key={group.title} title={group.title}>
          <div className={css.words}>
            {group.words.map(word => (
              <span key={word.lemma} className={css.learningWord}>
                {word.lemma}
                {word.detail && <span className={css.wordDetail}>{word.detail}</span>}
              </span>
            ))}
          </div>
        </Group>
      ))}
    </>
  )
}

export function UnknownWords({ store }: { store: SettingsStore }) {
  return (
    <WordList
      words={store.unknownWords.map(word => ({
        key: unknownWordKey(word.id),
        label: word.lemma,
        details: [],
        onRemove: () => void store.deleteUnknownWord(word.id),
      }))}
      hint={UNKNOWN_WORDS_HINT}
      empty="No unknown words yet. Mark them from a card: Report → More than one unknown word."
      deletingKey={store.deletingKey}
    />
  )
}
