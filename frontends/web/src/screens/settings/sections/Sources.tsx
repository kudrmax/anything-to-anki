import { Trash2 } from 'lucide-react'
import type { SourceMediaStats } from '@/api/types'
import { formatBytes } from '@/lib/text/format'
import { Button, DividerRow, Field, IconButton, Menu, Text } from '@/ui'
import type { SettingsStore } from '../useSettings'
import css from '../settings.module.css'
import { Group } from './Group'
import type { SectionProps } from './types'

export function Sources({ store, form }: SectionProps) {
  return (
    <>
      <Group>
        <DividerRow last label="Default titles" hint="Titles when one add makes several sources: {{collection}} — the collection, {{n}} — number in order, {{title}} — the file's or chapter's own title.">
          <div className={css.control}>
            <Field value={form.naming_rule} onChange={e => store.setField('naming_rule', e.target.value)} />
          </div>
        </DividerRow>
      </Group>
      <MediaStorage store={store} />
    </>
  )
}

function MediaSize({ bytes, count }: { bytes: number; count: number | null }) {
  return (
    <span className={css.mediaCell}>
      <span>{formatBytes(bytes)}</span>
      {count ? <Text tone="muted" size="s">{count} {count === 1 ? 'file' : 'files'}</Text> : null}
    </span>
  )
}

function MediaStorage({ store }: { store: SettingsStore }) {
  const { mediaStats } = store
  const totalImages = mediaStats.reduce((sum, s) => sum + s.screenshot_bytes, 0)
  const totalAudio = mediaStats.reduce((sum, s) => sum + s.audio_bytes, 0)
  const refresh = <Button variant="link" busy={store.mediaStatsLoading} onClick={() => void store.loadMediaStats()}>Refresh</Button>

  if (mediaStats.length === 0) {
    return (
      <Group title="Media storage">
        <DividerRow last label={<Text tone="muted">No video sources with media yet.</Text>}>{refresh}</DividerRow>
      </Group>
    )
  }
  return (
    <Group title="Media storage" hint="Screenshots and audio cut from each video source.">
      <div className={css.media}>
        <div className={css.mediaHead}>
          <span>Source</span>
          <span>Images</span>
          <span>Audio</span>
          <span />
        </div>
        {mediaStats.map(source => (
          <div key={source.source_id} className={css.mediaRow}>
            <span className={css.mediaTitle}><span className={css.ellipsis}>{source.source_title}</span></span>
            <MediaSize bytes={source.screenshot_bytes} count={source.screenshot_count} />
            <MediaSize bytes={source.audio_bytes} count={source.audio_count} />
            <MediaActions store={store} source={source} />
          </div>
        ))}
        <div className={`${css.mediaRow} ${css.mediaTotal}`}>
          <span className={css.mediaTitle}>Total</span>
          <MediaSize bytes={totalImages} count={null} />
          <MediaSize bytes={totalAudio} count={null} />
          {refresh}
        </div>
      </div>
    </Group>
  )
}

function MediaActions({ store, source }: { store: SettingsStore; source: SourceMediaStats }) {
  const hasImages = source.screenshot_bytes > 0
  const hasAudio = source.audio_bytes > 0
  return (
    <Menu
      trigger={<IconButton icon={Trash2} label="Delete media" disabled={!hasImages && !hasAudio} />}
      items={[
        { label: 'Delete images', danger: true, disabled: !hasImages, onSelect: () => void store.cleanupMedia(source.source_id, 'images') },
        { label: 'Delete audio', danger: true, disabled: !hasAudio, onSelect: () => void store.cleanupMedia(source.source_id, 'audio') },
        { label: 'Delete all', danger: true, separated: true, onSelect: () => void store.cleanupMedia(source.source_id, 'all') },
      ]}
    />
  )
}
