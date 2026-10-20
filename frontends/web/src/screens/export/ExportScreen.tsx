import { useLocation, useSearchParams } from 'react-router-dom'
import type { ExportGroup, ExportSection, SetScope } from '@/api/types'
import { backIn } from '@/lib/backLink'
import { parseSetScope } from '@/lib/scope'
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

/** Экспорт набора: у каждого набора свой экземпляр, состояние одного не переходит в другой. */
export function ExportScreen() {
  const [params] = useSearchParams()
  const scope = parseSetScope(params.get('scope'))
  return <ExportView key={String(scope)} scope={scope} />
}

function ExportView({ scope }: { scope: SetScope }) {
  const exporter = useExport(scope)
  const player = useAudioPlayer()
  // Стрелка «назад» — только если экран, открывший экспорт, сказал куда; из верхнего меню её нет.
  const back = backIn(useLocation().state, undefined)
  const title = scope !== 'all' && exporter.title ? exporter.title : 'Export'

  if (exporter.loading) {
    return <Page wide header={<PageHeader title={title} back={back} />}><Empty><Spinner /></Empty></Page>
  }

  const { ankiStatus, groups, counts, totalCards, exportedCount, settings, result } = exporter
  // Колонка превью нужна всем строкам, если видео есть хоть у одной: иначе колонки разъезжаются.
  const withMedia = [...groups.ready, ...groups.incomplete]
    .some(section => section.cards.some(card => card.screenshot_url || card.audio_url))
  const ankiLabel = ankiStatus === null ? 'Checking…' : ankiStatus.available ? 'Anki connected' : 'Anki unavailable'

  const header = (
    <PageHeader
      title={title}
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
        <Empty flush>
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
          <ExportSections sections={groups[group]} withMedia={withMedia} player={player} />
        </section>
      ))}
    </Page>
  )
}

interface ExportSectionsProps {
  sections: ExportSection[]
  withMedia: boolean
  player: AudioPlayer
}

function ExportSections({ sections, withMedia, player }: ExportSectionsProps) {
  return sections.map(section => (
    <section key={section.source_id} className={css.group}>
      <h3 className={css.groupTitle}>{section.source_title}<span>{section.cards.length}</span></h3>
      {section.cards.map(card => (
        <ExportCardRow key={card.candidate_id} card={card} sourceId={section.source_id} withMedia={withMedia} player={player} />
      ))}
    </section>
  ))
}
