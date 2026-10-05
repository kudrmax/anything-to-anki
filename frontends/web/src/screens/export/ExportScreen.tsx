import { useParams } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useAudioPlayer } from '@/lib/useAudioPlayer'
import { Page, PageHeader } from '@/shell'
import { Banner, Button, Empty, IconButton, Spinner, Stat, StatGrid, StatusDot, Text, Toast } from '@/ui'
import { ExportCardRow } from './ExportCardRow'
import { useExport } from './useExport'
import css from './export.module.css'

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

  const { ankiStatus, sections, exportedCount, settings, result, totalCards } = exporter
  // Колонка превью нужна всем строкам, если видео есть хоть у одной: иначе колонки разъезжаются.
  const withMedia = sections.some(section => section.cards.some(card => card.screenshot_url || card.audio_url))
  const ankiLabel = ankiStatus === null ? 'Checking…' : ankiStatus.available ? 'Anki connected' : 'Anki unavailable'

  const header = (
    <PageHeader
      title="Export"
      back={back}
      meta={<><StatusDot tone={ankiStatus === null ? 'idle' : ankiStatus.available ? 'ok' : 'err'} />{ankiLabel}</>}
    >
      <IconButton icon={Sparkles} label="Generate missing meanings" busy={exporter.generatingAll} disabled={!exporter.canGenerateAll} onClick={() => void exporter.generateAll()} />
      <Button variant="fill" busy={exporter.syncing} disabled={!exporter.canSync} onClick={() => void exporter.sync()}>
        Add to Anki · {totalCards} {totalCards === 1 ? 'card' : 'cards'}
      </Button>
    </PageHeader>
  )

  const aside = (
    <>
      <StatGrid>
        <Stat value={`${exporter.readyCards} / ${totalCards}`} label="ready to export" progress={totalCards > 0 ? exporter.readyCards / totalCards : 0} wide />
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
      {sections.map(section => (
        <section key={section.source_id} className={css.group}>
          {sourceId === undefined && (
            <h2 className={css.groupTitle}>{section.source_title}<span>{section.cards.length}</span></h2>
          )}
          {section.cards.map(card => (
            <ExportCardRow
              key={card.candidate_id}
              card={card}
              withMedia={withMedia}
              generating={exporter.generatingIds.has(card.candidate_id)}
              onGenerate={candidateId => void exporter.generate(candidateId)}
              player={player}
            />
          ))}
          </section>
      ))}
      <Toast message={exporter.toast} />
    </Page>
  )
}
