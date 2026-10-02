import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GripVertical } from 'lucide-react'
import type { FrequentWordThresholdOption, Settings } from '@/api/types'
import { autoPlayAudioPref, type ThemePref } from '@/lib/preferences'
import { formatBytes } from '@/lib/text/format'
import { useTheme } from '@/lib/theme'
import { Button, Chip, DividerRow, Empty, Field, Icon, Label, Range, RemovableChip, Segmented, Select, Spinner, Stack, Switch, Text } from '@/ui'
import type { SettingsStore, TemplatePart } from './useSettings'
import css from './settings.module.css'

const THEMES: { value: ThemePref; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]
const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => ({ value: level, label: level }))
const AUTO_THRESHOLD = 'auto'
const frequentWordThresholdLabel = ({ value, zipf, examples }: FrequentWordThresholdOption) => {
  if (value === AUTO_THRESHOLD) return `Auto — now ${zipf?.toFixed(1)}`
  return examples.length > 0 ? `${value} — ${examples.join(', ')}` : 'Off'
}
const AI_MODELS = [
  { value: 'haiku', label: 'Haiku' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'opus', label: 'Opus' },
]
const FIELD_MAPPING: { key: keyof Settings; label: string }[] = [
  { key: 'anki_field_sentence', label: 'Sentence' },
  { key: 'anki_field_target_word', label: 'Target word' },
  { key: 'anki_field_meaning', label: 'Meaning' },
  { key: 'anki_field_ipa', label: 'IPA' },
  { key: 'anki_field_image', label: 'Image' },
  { key: 'anki_field_audio', label: 'Audio' },
  { key: 'anki_field_translation', label: 'Translation' },
  { key: 'anki_field_synonyms', label: 'Synonyms' },
  { key: 'anki_field_examples', label: 'Examples' },
  { key: 'anki_field_audio_target_us', label: 'Audio US' },
  { key: 'anki_field_audio_target_uk', label: 'Audio UK' },
  { key: 'anki_field_audio_tts', label: 'Audio TTS' },
]
const TEMPLATE_PARTS: { part: TemplatePart; label: string }[] = [
  { part: 'front', label: 'Copy Front' },
  { part: 'back', label: 'Copy Back' },
  { part: 'css', label: 'Copy CSS' },
]
const USAGE_GROUP_LABELS: Record<string, string> = {
  neutral: 'Standard, unmarked words',
  informal: 'Slang, casual speech',
  formal: 'Formal register',
  specialized: 'Technical, domain-specific',
  connotation: 'Disapproving, approving, humorous',
  'old-fashioned': 'Dated, archaic',
  offensive: 'Offensive language',
  other: 'Literary, trademark, etc.',
}
const TTS_SPEED = { min: 0.5, max: 2.0, step: 0.1, fallback: 1.0 }
const TTS_VOICES: { id: string; label: string; accent: string; gender: string }[] = [
  { id: 'af_heart', label: 'Heart', accent: 'US', gender: 'F' },
  { id: 'af_alloy', label: 'Alloy', accent: 'US', gender: 'F' },
  { id: 'af_aoede', label: 'Aoede', accent: 'US', gender: 'F' },
  { id: 'af_bella', label: 'Bella', accent: 'US', gender: 'F' },
  { id: 'af_jessica', label: 'Jessica', accent: 'US', gender: 'F' },
  { id: 'af_kore', label: 'Kore', accent: 'US', gender: 'F' },
  { id: 'af_nicole', label: 'Nicole', accent: 'US', gender: 'F' },
  { id: 'af_nova', label: 'Nova', accent: 'US', gender: 'F' },
  { id: 'af_river', label: 'River', accent: 'US', gender: 'F' },
  { id: 'af_sarah', label: 'Sarah', accent: 'US', gender: 'F' },
  { id: 'af_sky', label: 'Sky', accent: 'US', gender: 'F' },
  { id: 'am_adam', label: 'Adam', accent: 'US', gender: 'M' },
  { id: 'am_echo', label: 'Echo', accent: 'US', gender: 'M' },
  { id: 'am_eric', label: 'Eric', accent: 'US', gender: 'M' },
  { id: 'am_fenrir', label: 'Fenrir', accent: 'US', gender: 'M' },
  { id: 'am_liam', label: 'Liam', accent: 'US', gender: 'M' },
  { id: 'am_michael', label: 'Michael', accent: 'US', gender: 'M' },
  { id: 'am_onyx', label: 'Onyx', accent: 'US', gender: 'M' },
  { id: 'am_puck', label: 'Puck', accent: 'US', gender: 'M' },
  { id: 'am_santa', label: 'Santa', accent: 'US', gender: 'M' },
  { id: 'bf_alice', label: 'Alice', accent: 'GB', gender: 'F' },
  { id: 'bf_emma', label: 'Emma', accent: 'GB', gender: 'F' },
  { id: 'bf_isabella', label: 'Isabella', accent: 'GB', gender: 'F' },
  { id: 'bf_lily', label: 'Lily', accent: 'GB', gender: 'F' },
  { id: 'bm_daniel', label: 'Daniel', accent: 'GB', gender: 'M' },
  { id: 'bm_fable', label: 'Fable', accent: 'GB', gender: 'M' },
  { id: 'bm_george', label: 'George', accent: 'GB', gender: 'M' },
  { id: 'bm_lewis', label: 'Lewis', accent: 'GB', gender: 'M' },
]

interface SectionProps {
  store: SettingsStore
  form: Settings
}

export function Appearance() {
  const { pref, setPref } = useTheme()
  return (
    <DividerRow last label="Theme">
      <Segmented value={pref} options={THEMES} onChange={setPref} />
    </DividerRow>
  )
}

export function Anki({ store, form }: SectionProps) {
  const text = (key: keyof Settings) => form[key] as string
  return (
    <>
      <DividerRow label="Deck name">
        <div className={css.control}><Field value={form.anki_deck_name} onChange={e => store.setField('anki_deck_name', e.target.value)} /></div>
      </DividerRow>
      <DividerRow label="Note type" hint="«AnythingToAnkiType» is created automatically. Use your own type for custom fields.">
        <div className={css.control}><Field value={form.anki_note_type} onChange={e => store.setField('anki_note_type', e.target.value)} /></div>
      </DividerRow>
      <Label>Field mapping</Label>
      <div className={css.map}>
        {FIELD_MAPPING.map(({ key, label }) => (
          <label key={key}>
            <span>{label}</span>
            <Field value={text(key)} onChange={e => store.setField(key, e.target.value)} />
          </label>
        ))}
      </div>
      <DividerRow
        label={
          <Stack row gap="m" wrap>
            {store.verifyResult && (store.verifyResult.valid
              ? <Text tone="ok">✓ Valid</Text>
              : <Text tone="err">Missing: {store.verifyResult.missing_fields.join(', ')}</Text>)}
            {store.verifyError && <Text tone="err">{store.verifyError}</Text>}
            {store.createResult && <Text tone="ok">{store.createResult.already_existed ? 'Already exists' : 'Created ✓'}</Text>}
            {store.createError && <Text tone="err">{store.createError}</Text>}
          </Stack>
        }
      >
        <Button busy={store.verifying} disabled={!form.anki_note_type.trim()} onClick={() => void store.verify()}>Verify note type</Button>
        <Button busy={store.creating} disabled={!form.anki_note_type.trim()} onClick={() => void store.createNoteType()}>Create type</Button>
      </DividerRow>
      <DividerRow last label="Card template" hint="Copy and paste into Anki's card template editor. Field names match your mapping above.">
        {TEMPLATE_PARTS.map(({ part, label }) => (
          <Button key={part} variant="link" onClick={() => void store.copyTemplate(part)}>
            {store.copiedTemplate === part ? 'Copied' : label}
          </Button>
        ))}
      </DividerRow>
    </>
  )
}

export function Vocabulary({ store, form }: SectionProps) {
  const navigate = useNavigate()
  const bootstrap = store.bootstrapStatus
  return (
    <>
      <DividerRow label="Target CEFR level" hint="Words above this level will be suggested as candidates.">
        <Segmented value={form.cefr_level} options={CEFR_LEVELS} onChange={level => store.setField('cefr_level', level)} />
      </DividerRow>
      <DividerRow
        label="Frequent words"
        hint="Words at least this frequent go to the bottom of the list as probably known. Auto learns the value from your Know / Learn marks. Other options show examples of words that go down; lower value — more words go down."
      >
        <Select value={form.frequent_word_threshold} onChange={e => store.setField('frequent_word_threshold', e.target.value)}>
          {store.frequentWordThresholds.map(option => (
            <option key={option.value} value={option.value}>{frequentWordThresholdLabel(option)}</option>
          ))}
        </Select>
      </DividerRow>
      <DividerRow
        label="Vocabulary calibration"
        hint={
          bootstrap?.status === 'ready' ? `Ready — ${bootstrap.word_count} words, built ${bootstrap.built_at ? new Date(bootstrap.built_at).toLocaleDateString() : '—'}`
            : bootstrap?.status === 'error' ? <Text tone="err">{bootstrap.error ?? 'Build failed'}</Text>
              : bootstrap?.status === 'building' ? 'Building word list…'
                : 'Build a word list to calibrate what you already know.'
        }
      >
        {bootstrap?.status === 'building' && <Spinner />}
        {bootstrap?.status === 'none' && <Button onClick={() => void store.buildBootstrap()}>Prepare</Button>}
        {bootstrap?.status === 'error' && <Button onClick={() => void store.buildBootstrap()}>Retry</Button>}
        {bootstrap?.status === 'ready' && (
          <>
            <Button variant="link" onClick={() => void store.buildBootstrap()}>Rebuild</Button>
            <Button onClick={() => navigate('/calibrate')}>Calibrate</Button>
          </>
        )}
      </DividerRow>
      <UsagePriority store={store} form={form} />
    </>
  )
}

function UsagePriority({ store, form }: SectionProps) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dropIndex, setDropIndex] = useState<number | null>(null)
  const dragCounter = useRef(0)
  const order = form.usage_group_order ?? Object.keys(USAGE_GROUP_LABELS)

  const drop = (fromIndex: number, toIndex: number) => {
    if (Number.isNaN(fromIndex) || fromIndex === toIndex) return
    const next = [...order]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    store.reorderUsageGroups(next)
  }

  return (
    <>
      <Label>Usage priority — drag to reorder</Label>
      {order.map((group, index) => (
        <DividerRow
          key={group}
          compact
          last={index === order.length - 1}
          lead={<Icon as={GripVertical} size="s" />}
          label={
            <span className={css.named}>
              <span className={css.name}>{group}</span>
              <Text tone="muted" size="s">{USAGE_GROUP_LABELS[group]}</Text>
            </span>
          }
          state={dragIndex === index ? 'dragging' : dropIndex === index ? 'target' : undefined}
          draggable
          onDragStart={e => { setDragIndex(index); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(index)) }}
          onDragEnd={() => { setDragIndex(null); setDropIndex(null); dragCounter.current = 0 }}
          onDragEnter={() => { dragCounter.current++; setDropIndex(index) }}
          onDragLeave={() => { dragCounter.current--; if (dragCounter.current <= 0) { setDropIndex(null); dragCounter.current = 0 } }}
          onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}
          onDrop={e => {
            e.preventDefault()
            dragCounter.current = 0
            setDropIndex(null)
            drop(parseInt(e.dataTransfer.getData('text/plain'), 10), index)
          }}
        />
      ))}
    </>
  )
}

export function ReviewPrefs() {
  const [autoPlay, setAutoPlay] = useState<boolean>(() => autoPlayAudioPref.read())
  const toggle = (next: boolean) => { setAutoPlay(next); autoPlayAudioPref.write(next) }
  return (
    <DividerRow last label="Auto-play audio" hint="After marking a word, automatically play the next word's audio (if available).">
      <Switch checked={autoPlay} onChange={toggle} label="Auto-play audio" />
    </DividerRow>
  )
}

export function AiModel({ store, form }: SectionProps) {
  return (
    <DividerRow last label="Claude" hint="Reserved for future AI-powered features.">
      <Segmented value={form.ai_model} options={AI_MODELS} onChange={model => store.setField('ai_model', model)} />
    </DividerRow>
  )
}

const VOICES_PREVIEW = 7

export function Tts({ store, form }: SectionProps) {
  const [showAllVoices, setShowAllVoices] = useState(false)
  const speed = form.tts_speed ?? TTS_SPEED.fallback
  const enabled = form.tts_enabled_voices ?? TTS_VOICES.map(voice => voice.id)
  const toggle = (id: string) => store.setField('tts_enabled_voices', enabled.includes(id) ? enabled.filter(v => v !== id) : [...enabled, id])
  return (
    <>
      <DividerRow label="Speed">
        <Text tone="muted" size="s">{speed.toFixed(1)}×</Text>
        <Range min={TTS_SPEED.min} max={TTS_SPEED.max} step={TTS_SPEED.step} value={speed} onChange={e => store.setField('tts_speed', parseFloat(e.target.value))} />
      </DividerRow>
      <Label>Enabled voices — random selection from checked</Label>
      <Stack row wrap>
        {(showAllVoices ? TTS_VOICES : TTS_VOICES.slice(0, VOICES_PREVIEW)).map(voice => (
          <Chip key={voice.id} outlined on={enabled.includes(voice.id)} onClick={() => toggle(voice.id)}>
            {voice.label} · {voice.accent} {voice.gender}
          </Chip>
        ))}
        {!showAllVoices && (
          <Button variant="link" onClick={() => setShowAllVoices(true)}>+ {TTS_VOICES.length - VOICES_PREVIEW} more</Button>
        )}
      </Stack>
    </>
  )
}

export function KnownWords({ store }: { store: SettingsStore }) {
  return (
    <>
      {store.knownWords.length === 0 ? <Empty>No known words yet.</Empty> : (
        <Stack row wrap>
          {store.knownWords.map(word => (
            <RemovableChip
              key={word.id}
              label={`${word.lemma} · ${word.pos ?? 'any'}`}
              disabled={store.deletingId === word.id}
              onRemove={() => void store.deleteWord(word.id)}
            />
          ))}
        </Stack>
      )}
      <Label>Known words won't be suggested when processing new sources.</Label>
    </>
  )
}

export function MediaStorage({ store }: { store: SettingsStore }) {
  const { mediaStats } = store
  const totalImages = mediaStats.reduce((sum, s) => sum + s.screenshot_bytes, 0)
  const totalAudio = mediaStats.reduce((sum, s) => sum + s.audio_bytes, 0)
  const sizes = (images: number, imageCount: number | null, audio: number, audioCount: number | null) =>
    `${formatBytes(images)}${imageCount ? ` (${imageCount})` : ''} images · ${formatBytes(audio)}${audioCount ? ` (${audioCount})` : ''} audio`

  if (mediaStats.length === 0) {
    return (
      <DividerRow last label={<Text tone="muted">No video sources with media yet.</Text>}>
        <Button variant="link" busy={store.mediaStatsLoading} onClick={() => void store.loadMediaStats()}>Refresh</Button>
      </DividerRow>
    )
  }
  return (
    <>
      {mediaStats.map(source => (
        <DividerRow key={source.source_id} label={source.source_title}>
          <Text tone="muted" size="s">{sizes(source.screenshot_bytes, source.screenshot_count, source.audio_bytes, source.audio_count)}</Text>
          {source.screenshot_bytes > 0 && <Button variant="danger-link" onClick={() => void store.cleanupMedia(source.source_id, 'images')}>Del images</Button>}
          {source.audio_bytes > 0 && <Button variant="danger-link" onClick={() => void store.cleanupMedia(source.source_id, 'audio')}>Del audio</Button>}
          {source.screenshot_bytes + source.audio_bytes > 0 && <Button variant="danger-link" onClick={() => void store.cleanupMedia(source.source_id, 'all')}>Del all</Button>}
        </DividerRow>
      ))}
      <DividerRow last label={<b>Total</b>}>
        <Text tone="muted" size="s">{sizes(totalImages, null, totalAudio, null)}</Text>
        <Button variant="link" busy={store.mediaStatsLoading} onClick={() => void store.loadMediaStats()}>Refresh</Button>
      </DividerRow>
    </>
  )
}
