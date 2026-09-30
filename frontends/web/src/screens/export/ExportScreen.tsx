import { useParams } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useAudioPlayer } from '@/lib/useAudioPlayer'
import { Aside, Page, PageHeader } from '@/shell'
import { Banner, Button, DividerRow, Empty, GroupLabel, Icon, Spinner, StatusDot, Text, Toast } from '@/ui'
import { ExportCardRow } from './ExportCardRow'
import { useExport } from './useExport'

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
    return <Page header={<PageHeader title="Export" back={back} />}><Empty><Spinner /></Empty></Page>
  }

  const { ankiStatus, sections, settings, result, totalCards } = exporter
  const ankiLabel = ankiStatus === null ? 'Checking…' : ankiStatus.available ? 'Anki connected' : 'Anki unavailable'

  const header = (
    <PageHeader
      title="Export"
      back={back}
      meta={<><StatusDot tone={ankiStatus === null ? 'idle' : ankiStatus.available ? 'ok' : 'err'} />{ankiLabel}</>}
    >
      <Button variant="link" busy={exporter.generatingAll} disabled={!exporter.canGenerateAll} onClick={() => void exporter.generateAll()}>
        <Icon as={Sparkles} size="s" />Generate missing
      </Button>
      <Button variant="fill" busy={exporter.syncing} disabled={!exporter.canSync} onClick={() => void exporter.sync()}>
        Add to Anki · {totalCards} {totalCards === 1 ? 'card' : 'cards'}
      </Button>
    </PageHeader>
  )

  const aside = (
    <>
      <Aside title="Destination">
        <DividerRow compact label="Deck"><b>{settings?.anki_deck_name ?? '—'}</b></DividerRow>
        <DividerRow compact label="Note type"><b>{settings?.anki_note_type ?? '—'}</b></DividerRow>
        <DividerRow compact label="Ready"><b>{exporter.readyCards} of {totalCards}</b></DividerRow>
        <DividerRow compact last label="Sources"><b>{sections.length}</b></DividerRow>
      </Aside>
      {result && (
        <Aside title="Last sync">
          <DividerRow compact label="Added"><b>{result.added}</b></DividerRow>
          <DividerRow compact label="Skipped" hint={result.skipped_lemmas.length > 0 && `Already in Anki: ${result.skipped_lemmas.join(', ')}`}>
            <b>{result.skipped}</b>
          </DividerRow>
          <DividerRow compact last label="Errors" hint={result.error_lemmas.length > 0 && <Text tone="err">Failed: {result.error_lemmas.join(', ')}</Text>}>
            <b>{result.errors}</b>
          </DividerRow>
        </Aside>
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
    <Page header={header} aside={aside} banner={(exporter.error || ankiStatus?.available === false) ? banner : undefined}>
      {totalCards === 0 && <Empty>No words marked for learning. Go to the review page and mark words as “Learn”.</Empty>}
      {sections.map(section => (
        <div key={section.source_id}>
          {sourceId === undefined && (
            <GroupLabel>{section.source_title} · {section.cards.length} {section.cards.length === 1 ? 'card' : 'cards'}</GroupLabel>
          )}
          {section.cards.map(card => (
            <ExportCardRow
              key={card.candidate_id}
              card={card}
              generating={exporter.generatingIds.has(card.candidate_id)}
              onGenerate={candidateId => void exporter.generate(candidateId)}
              player={player}
            />
          ))}
        </div>
      ))}
      <Toast message={exporter.toast} />
    </Page>
  )
}
