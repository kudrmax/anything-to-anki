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

/** Числа превью и итога — что пользователь увидит в своих карточках; нулевые строки не показываются. */
function countLines(counts: RebuildCounts): string[] {
  const lines = [
    counts.words_added > 0 && (counts.words_added === 1 ? '1 new word gets a card' : `${counts.words_added} new words get cards`),
    counts.words_removed > 0 && (counts.words_removed === 1
      ? '1 card removed: its word is no longer new to you'
      : `${counts.words_removed} cards removed: their words are no longer new to you`),
    counts.cards_lost_generation > 0 && (counts.cards_lost_generation === 1
      ? '1 removed card loses its Polish, Meaning and audio'
      : `${counts.cards_lost_generation} removed cards lose their Polish, Meaning and audio`),
    counts.cards_became_ready > 0 && (counts.cards_became_ready === 1
      ? '1 card becomes ready: every other word in it is familiar now'
      : `${counts.cards_became_ready} cards become ready: every other word in them is familiar now`),
    counts.cards_left_ready > 0 && (counts.cards_left_ready === 1
      ? '1 card is no longer ready: it has other new words again'
      : `${counts.cards_left_ready} cards are no longer ready: they have other new words again`),
    counts.cards_moved > 0 && (counts.cards_moved === 1
      ? '1 card switches to an easier sentence; run ✨ for it again'
      : `${counts.cards_moved} cards switch to easier sentences; run ✨ for them again`),
    counts.cards_recut > 0 && `${plural(counts.cards_recut, 'card gets', 'cards get')} a different phrase`,
    counts.cards_recut_lost_text_generation > 0 && `${counts.cards_recut_lost_text_generation} of them ${counts.cards_recut_lost_text_generation === 1 ? 'loses' : 'lose'} Polish and audio`,
  ].filter((line): line is string => Boolean(line))
  return lines.length > 0 ? lines : [UNSEEN_CHANGES]
}

function refreshLines(refresh: TopicRefreshSummary): string[] {
  return [`${plural(refresh.words_added, 'word', 'words')} and ${plural(refresh.phrases_added, 'phrase', 'phrases')} added`]
}

const Lines = ({ lines }: { lines: string[] }) => (
  <ul className={css.operationLines}>{lines.map(line => <li key={line}>{line}</li>)}</ul>
)

const NOTHING_TO_CHANGE = 'Nothing to change: your cards already match the words you know.'
const UNSEEN_CHANGES = 'Your cards stay as they are; only behind-the-scenes data gets refreshed.'

/** Что меняется; ничего не меняется — одна строка, а не список. */
const Counts = ({ counts, outcome }: { counts: RebuildCounts; outcome: SetOutcome }) => {
  const notReached = outcomeLines(outcome)
  return (
    <>
      {counts.nothing_to_update ? <Text>{NOTHING_TO_CHANGE}</Text> : <Lines lines={countLines(counts)} />}
      {notReached.length > 0 && <Lines lines={notReached} />}
    </>
  )
}

const TITLE: Record<SetOperation, (title: string) => string> = {
  update: title => `Find words again in “${title}”`,
  recut: title => `Process “${title}” again`,
  refresh: title => `Refresh “${title}”`,
}

const ABOUT: Record<RebuildMode, string> = {
  update: 'Looks for words to learn again, by the words you know, your Unknown list, your level and the app’s current rules. Adds cards for new words, removes cards whose word is no longer new to you, and moves cards to easier sentences. The phrases of your cards stay, with their Polish, Meaning and audio.',
  recut: 'Processes the text again, as when you added it: splits it into phrases again and finds the words to learn. Your decisions stay. A card whose phrase comes out different loses its Polish and audio; Meaning stays.',
}

/** Find words again, Process again с превью или Refresh темы: запуск, прогресс и итог. Что меняется, считает backend. */
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
    return <>{close}<Button variant="fill" onClick={() => void start(() => api.rebuild(scope, operation))}>{operation === 'update' ? 'Find words again' : 'Process again'}</Button></>
  })()

  const body = (() => {
    if (run.phase === 'failed') return <Banner tone="err">{run.error}</Banner>
    if (running) return <span className={css.caption}><Spinner /><Text tone="muted">{run.caption}</Text></span>
    const { summary, refresh } = finished ? run.operation : { summary: null, refresh: null }
    if (summary) return <Counts counts={summary.counts} outcome={summary} />
    if (refresh) return <Lines lines={[...refreshLines(refresh), ...outcomeLines(refresh)]} />
    if (operation === 'refresh') {
      return <Text tone="muted">Looks for the words of {oneSource ? 'the topic' : 'the topics here'} in sources added later. New phrases are only added: decisions, generation and cards you worked on stay.</Text>
    }
    if (!counts || !preview) return <Text tone="muted">{ABOUT[operation]}</Text>
    return (
      <>
        <Counts counts={counts} outcome={preview} />
        {!counts.nothing_to_update && <Text tone="muted" size="s">The numbers are an estimate and may differ by a few cards.</Text>}
      </>
    )
  })()

  return (
    <Modal title={TITLE[operation](title)} onClose={onClose} footer={footer}>
      {body}
    </Modal>
  )
}
