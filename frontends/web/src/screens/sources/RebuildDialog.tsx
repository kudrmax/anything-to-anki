import { useEffect, useRef } from 'react'
import { api } from '@/api/client'
import type { RebuildCounts, RebuildMode, SetOperation, SetOutcome, SetScope, TopicRefreshSummary } from '@/api/types'
import { isSourceScope } from '@/lib/scope'
import { Banner, Button, Modal, Spinner, Text } from '@/ui'
import { useScopeOperation } from './useScopeOperation'
import css from './sources.module.css'

interface RebuildDialogProps {
  /** Источник (набор из одного), коллекция, Unsorted или All: логика одна. */
  scope: SetScope
  title: string
  operation: SetOperation
  /** Операция закончилась: список источников и открытые экраны перечитываются. */
  onFinished: () => void
  onClose: () => void
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

/** Источники набора, которые не дошли до операции; у одного источника строк нет. */
function outcomeLines(outcome: SetOutcome): string[] {
  return [
    outcome.skipped > 0 && `${plural(outcome.skipped, 'source was', 'sources were')} busy and skipped`,
    outcome.failed > 0 && `${plural(outcome.failed, 'source', 'sources')} failed`,
  ].filter((line): line is string => Boolean(line))
}

/** Числа превью и итога: слова, удалённые и переехавшие карточки, заново нарезанные фразы. */
function countLines(counts: RebuildCounts): string[] {
  if (counts.nothing_to_update) return [UP_TO_DATE]
  return [
    `${plural(counts.words_added, 'new word', 'new words')}, ${plural(counts.words_removed, 'word removed', 'words removed')}`,
    counts.cards_lost_generation > 0 && `${plural(counts.cards_lost_generation, 'removed card had', 'removed cards had')} Polish, Meaning or audio`,
    counts.cards_moved > 0 && `${plural(counts.cards_moved, 'card moves', 'cards move')} to a simpler sentence — need ✨ there`,
    counts.cards_recut > 0 && `${plural(counts.cards_recut, 'phrase gets', 'phrases get')} a new cut`,
    counts.cards_recut_lost_text_generation > 0 && `${counts.cards_recut_lost_text_generation} of them lose Polish or audio`,
  ].filter((line): line is string => Boolean(line))
}

function refreshLines(refresh: TopicRefreshSummary): string[] {
  return [`${plural(refresh.words_added, 'word', 'words')} and ${plural(refresh.phrases_added, 'phrase', 'phrases')} added`]
}

const Lines = ({ lines }: { lines: string[] }) => (
  <ul className={css.operationLines}>{lines.map(line => <li key={line}>{line}</li>)}</ul>
)

const UP_TO_DATE = 'Already up to date'

const TITLE: Record<SetOperation, (title: string) => string> = {
  update: title => `Update “${title}”`,
  recut: title => `Re-cut phrases of “${title}”`,
  refresh: title => `Refresh “${title}”`,
}

const ABOUT: Record<RebuildMode, string> = {
  update: 'Finds new words, removes words you no longer need and moves cards to simpler sentences. Phrase texts and their Polish, Meaning and audio stay.',
  recut: 'Also cuts every phrase again by the current logic. A phrase that changes loses its Polish, audio and video; Meaning stays.',
}

/** Update, Re-cut с превью или Refresh темы: запуск, прогресс и итог. Что меняется, считает backend. */
export function RebuildDialog({ scope, title, operation, onFinished, onClose }: RebuildDialogProps) {
  const { run, preview, start } = useScopeOperation(scope)
  const oneSource = isSourceScope(scope)

  const finished = run.phase === 'done' && run.operation.kind !== 'preview'
  const reported = useRef(false)
  useEffect(() => {
    if (!finished || reported.current) return
    reported.current = true
    onFinished()
  }, [finished, onFinished])

  const counts = preview?.counts ?? null
  const running = run.phase === 'running'
  const done = finished || running || Boolean(counts?.nothing_to_update)
  const close = <Button variant="link" onClick={onClose}>{done ? 'Close' : 'Cancel'}</Button>

  const footer = (() => {
    if (finished || running) return close
    if (operation === 'refresh') {
      return <>{close}<Button variant="fill" onClick={() => void start(() => api.refresh(scope))}>Refresh</Button></>
    }
    if (!counts) {
      return <>{close}<Button variant="fill" onClick={() => void start(() => api.previewRebuild(scope, operation))}>Preview</Button></>
    }
    if (counts.nothing_to_update) return close
    return <>{close}<Button variant="fill" onClick={() => void start(() => api.rebuild(scope, operation))}>{operation === 'update' ? 'Update' : 'Re-cut'}</Button></>
  })()

  const body = (() => {
    if (run.phase === 'failed') return <Banner tone="err">{run.error}</Banner>
    if (running) return <span className={css.caption}><Spinner /><Text tone="muted">{run.caption}</Text></span>
    const { summary, refresh } = finished ? run.operation : { summary: null, refresh: null }
    if (summary) return <Lines lines={[...countLines(summary.counts), ...outcomeLines(summary)]} />
    if (refresh) return <Lines lines={[...refreshLines(refresh), ...outcomeLines(refresh)]} />
    if (operation === 'refresh') {
      return <Text tone="muted">Looks for the words of {oneSource ? 'the topic' : 'the topics here'} in sources added later. New phrases are only added: decisions, generation and cards you worked on stay.</Text>
    }
    if (!counts || !preview) return <Text tone="muted">{ABOUT[operation]}</Text>
    return (
      <>
        <Lines lines={[...countLines(counts), ...outcomeLines(preview)]} />
        {!counts.nothing_to_update && <Text tone="muted" size="s">The numbers may differ slightly from the result.</Text>}
      </>
    )
  })()

  return (
    <Modal title={TITLE[operation](title)} onClose={onClose} footer={footer}>
      {body}
    </Modal>
  )
}
