import { useParams } from 'react-router-dom'
import type { ExportGroup, ExportSection } from '@/api/types'
import { useAudioPlayer, type AudioPlayer } from '@/lib/useAudioPlayer'
import { Page, PageHeader } from '@/shell'
import { Banner, Button, Empty, Spinner, Stat, StatGrid, StatusDot, Text } from '@/ui'
import { ExportCardRow } from './ExportCardRow'
import { useExport } from './useExport'
import css from './export.module.css'

const GROUPS: { group: ExportGroup; title: string; hint: string; action: string; variant: 'fill' | 'soft' }[] = [
  { group: 'ready', title: 'Ready', hint: 'Meaning and phrase audio are in place', action: 'Add to Anki', variant: 'fill' },
  { group: 'incomplete', title: 'Incomplete', hint: 'Open a card to fill in what is missing', action: 'Export incomplete', variant: 'soft' },
]

const cardsLabel = (count: number) => `${count} ${count === 1 ? 'card' : 'cards'}`

/** Общий экспорт и экспорт источника — разные экземпляры: состояние одного не переходит в другой. */
export function ExportScreen() {
  const { id } = useParams<{ id: string }>()
  return <ExportView key={id ?? 'all'} sourceId={id === undefined ? undefined : Number(id)} />
}

function ExportView({ sourceId }: { sourceId: number | undefined }) {
  const exporter = useExport(sourceId)
  const player = useAudioPlayer()
  const back = sourceId === undefined ? undefined : `/sources/${sourceId}/review`

  if (exporter.loading) {
    return <Page wide header={<PageHeader title="Export" back={back} />}><Empty><Spinner /></Empty></Page>
  }

  const { ankiStatus, groups, counts, totalCards, exportedCount, settings, result } = exporter
  // Колонка превью нужна всем строкам, если видео есть хоть у одной: иначе колонки разъезжаются.
  const withMedia = [...groups.ready, ...groups.incomplete]
    .some(section => section.cards.some(card => card.screenshot_url || card.audio_url))
  const ankiLabel = ankiStatus === null ? 'Checking…' : ankiStatus.available ? 'Anki connected' : 'Anki unavailable'

  const header = (
    <PageHeader
      title="Export"
      back={back}
      meta={<><StatusDot tone={ankiStatus === null ? 'idle' : ankiStatus.available ? 'ok' : 'err'} />{ankiLabel}</>}
    />
  )

  const aside = (
    <>
      <StatGrid>
        <Stat value={`${counts.ready} / ${totalCards}`} label="ready to export" progress={totalCards > 0 ? counts.ready / totalCards : 0} wide />
        <Stat small value={settings?.anki_deck_name ?? '—'} label="deck" />
        <Stat small value={settings?.anki_note_type ?? '—'} label="note type" />
        {exportedCount > 0 && <Stat small value={exportedCount} label="already exported" wide />}
      </StatGrid>
      {result && (
        <StatGrid>
          <Stat value={result.added} label="added" />
          <Stat value={result.skipped} label="already in Anki" hint={result.skipped_lemmas.length > 0 && result.skipped_lemmas.join(', ')} />
          {result.errors > 0 && (
            <Stat value={result.errors} label="failed" hint={<Text tone="err">{result.error_lemmas.join(', ')}</Text>} wide />
          )}
        </StatGrid>
      )}
    </>
  )

  const banner = (
    <>
      {exporter.error && <Banner tone="err">{exporter.error}</Banner>}
      {ankiStatus?.available === false && <Banner tone="warn">Launch Anki with AnkiConnect to sync</Banner>}
    </>
  )

  return (
    <Page wide header={header} aside={aside} banner={(exporter.error || ankiStatus?.available === false) ? banner : undefined}>
      {totalCards === 0 && (
        <Empty>
          {exportedCount > 0
            ? 'Everything marked for learning is already in Anki.'
            : 'No words marked for learning. Go to the review page and mark words as “Learn”.'}
        </Empty>
      )}
      {GROUPS.filter(({ group }) => counts[group] > 0).map(({ group, title, hint, action, variant }) => (
        <section key={group} className={css.exportGroup}>
          <header className={css.exportGroupHead}>
            <div>
              <h2 className={css.exportGroupTitle}>{title}<span>{counts[group]}</span></h2>
              <Text tone="muted" size="s">{hint}</Text>
            </div>
            <Button variant={variant} busy={exporter.syncing === group} disabled={!exporter.canSync(group)} onClick={() => void exporter.sync(group)}>
              {action} · {cardsLabel(counts[group])}
            </Button>
          </header>
          <ExportSections sections={groups[group]} showSourceTitles={sourceId === undefined} withMedia={withMedia} player={player} />
        </section>
      ))}
    </Page>
  )
}

interface ExportSectionsProps {
  sections: ExportSection[]
  showSourceTitles: boolean
  withMedia: boolean
  player: AudioPlayer
}

function ExportSections({ sections, showSourceTitles, withMedia, player }: ExportSectionsProps) {
  return sections.map(section => (
    <section key={section.source_id} className={css.group}>
      {showSourceTitles && (
        <h3 className={css.groupTitle}>{section.source_title}<span>{section.cards.length}</span></h3>
      )}
      {section.cards.map(card => (
        <ExportCardRow key={card.candidate_id} card={card} sourceId={section.source_id} withMedia={withMedia} player={player} />
      ))}
    </section>
  ))
}
