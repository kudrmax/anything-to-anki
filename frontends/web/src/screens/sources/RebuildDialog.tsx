import { useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { RebuildCounts, SourceSummary, TopicRefreshSummary } from '@/api/types'
import { Banner, Button, DividerRow, Modal, Spinner, Switch, Text } from '@/ui'
import { useSourceOperation } from './useSourceOperation'
import css from './sources.module.css'

type Operation = SourceSummary['available_operations'][number]

interface RebuildDialogProps {
  sourceId: number
  title: string
  operation: Operation
  /** Операция закончилась: список источников и открытые экраны перечитываются. */
  onFinished: () => void
  onClose: () => void
}

const ALSO_UNREVIEWED = 'Also unreviewed cards'

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

/** Числа превью: сколько слов появится и уйдёт, и что станет с генерацией. */
function previewLines(counts: RebuildCounts): string[] {
  return [
    `${plural(counts.words_added, 'word appears', 'words appear')}, ${plural(counts.words_removed, 'word goes', 'words go')}`,
    counts.cards_new_phrase > 0 && `${plural(counts.cards_new_phrase, 'card gets', 'cards get')} a different phrase — need ✨ again`,
    counts.cards_text_reset > 0 && `${plural(counts.cards_text_reset, 'card\'s', 'cards\'')} text changed — their generation is reset`,
  ].filter((line): line is string => Boolean(line))
}

/** Итог Rebuild: появилось / ушло / сменилась фраза / сколько карточек ждут ✨. */
function summaryLines(counts: RebuildCounts): string[] {
  if (counts.nothing_to_update) return ['Nothing changed']
  return [
    `${plural(counts.words_added, 'word appeared', 'words appeared')}, ${plural(counts.words_removed, 'word went', 'words went')}`,
    `${plural(counts.cards_new_phrase, 'card got', 'cards got')} a different phrase`,
    counts.cards_text_reset > 0 && `${plural(counts.cards_text_reset, 'card\'s', 'cards\'')} generation reset`,
    `${plural(counts.cards_without_generation, 'card', 'cards')} without generation — run ✨ in review`,
  ].filter((line): line is string => Boolean(line))
}

function refreshLines(refresh: TopicRefreshSummary): string[] {
  return [`${plural(refresh.words_added, 'word', 'words')} and ${plural(refresh.phrases_added, 'phrase', 'phrases')} added`]
}

const Lines = ({ lines }: { lines: string[] }) => (
  <ul className={css.operationLines}>{lines.map(line => <li key={line}>{line}</li>)}</ul>
)

/** Rebuild с превью или Refresh темы: запуск, прогресс и итог. Что меняется, считает backend. */
export function RebuildDialog({ sourceId, title, operation, onFinished, onClose }: RebuildDialogProps) {
  const { run, preview, start } = useSourceOperation(sourceId)
  const [includeOpen, setIncludeOpen] = useState(false)

  const finished = run.phase === 'done' && run.operation.kind !== 'preview'
  const reported = useRef(false)
  useEffect(() => {
    if (!finished || reported.current) return
    reported.current = true
    onFinished()
  }, [finished, onFinished])

  const withOpen = preview?.with_open ?? null
  const alsoOpen = withOpen !== null && includeOpen
  const counts = preview && (alsoOpen && withOpen ? withOpen : preview.without_open)
  const running = run.phase === 'running'
  const close = <Button variant="link" onClick={onClose}>{finished || running ? 'Close' : 'Cancel'}</Button>

  const footer = (() => {
    if (finished || running) return close
    if (operation === 'refresh') {
      return <>{close}<Button variant="fill" onClick={() => void start(() => api.refreshTopic(sourceId))}>Refresh</Button></>
    }
    if (!counts) {
      return <>{close}<Button variant="fill" onClick={() => void start(() => api.previewRebuild(sourceId))}>Preview</Button></>
    }
    if (counts.nothing_to_update) return close
    return <>{close}<Button variant="fill" onClick={() => void start(() => api.rebuildSource(sourceId, alsoOpen))}>Rebuild</Button></>
  })()

  const body = (() => {
    if (run.phase === 'failed') return <Banner tone="err">{run.error}</Banner>
    if (running) return <span className={css.caption}><Spinner /><Text tone="muted">{run.caption}</Text></span>
    if (finished && run.operation.summary) return <Lines lines={summaryLines(run.operation.summary.counts)} />
    if (finished && run.operation.refresh) return <Lines lines={refreshLines(run.operation.refresh)} />
    if (operation === 'refresh') {
      return <Text tone="muted">Looks for the topic’s words in sources added later. New phrases are only added: decisions, generation and cards you worked on stay.</Text>
    }
    if (!counts) {
      return <Text tone="muted">Rebuilds the source with the current selection logic, level and known words. Decisions and generated results are kept. Preview analyzes the whole source first.</Text>
    }
    return (
      <>
        {counts.nothing_to_update ? <Text>Nothing to update</Text> : <Lines lines={previewLines(counts)} />}
        {withOpen && (
          <DividerRow last label={ALSO_UNREVIEWED} hint="Cards with generation may also get a better phrase; the old phrase keeps its results.">
            <Switch checked={includeOpen} onChange={setIncludeOpen} label={ALSO_UNREVIEWED} />
          </DividerRow>
        )}
        <Text tone="muted" size="s">The numbers may differ slightly from the result.</Text>
      </>
    )
  })()

  return (
    <Modal title={`${operation === 'refresh' ? 'Refresh' : 'Rebuild'} “${title}”`} onClose={onClose} footer={footer}>
      {body}
    </Modal>
  )
}
