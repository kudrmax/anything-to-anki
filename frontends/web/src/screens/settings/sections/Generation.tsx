import { Chip, DividerRow, Range, Segmented, Text } from '@/ui'
import css from '../settings.module.css'
import { Group } from './Group'
import type { SectionProps } from './types'

const AI_MODELS = [
  { value: 'haiku', label: 'Haiku' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'opus', label: 'Opus' },
]
const TTS_SPEED = { min: 0.5, max: 2.0, step: 0.1, fallback: 1.0 }
const IMAGES_PER_SOURCE = { min: 1, max: 30, step: 1, fallback: 12 }

interface Voice {
  id: string
  label: string
}

const VOICE_GROUPS: { title: string; voices: Voice[] }[] = [
  {
    title: 'American female',
    voices: [
      { id: 'af_heart', label: 'Heart' },
      { id: 'af_alloy', label: 'Alloy' },
      { id: 'af_aoede', label: 'Aoede' },
      { id: 'af_bella', label: 'Bella' },
      { id: 'af_jessica', label: 'Jessica' },
      { id: 'af_kore', label: 'Kore' },
      { id: 'af_nicole', label: 'Nicole' },
      { id: 'af_nova', label: 'Nova' },
      { id: 'af_river', label: 'River' },
      { id: 'af_sarah', label: 'Sarah' },
      { id: 'af_sky', label: 'Sky' },
    ],
  },
  {
    title: 'American male',
    voices: [
      { id: 'am_adam', label: 'Adam' },
      { id: 'am_echo', label: 'Echo' },
      { id: 'am_eric', label: 'Eric' },
      { id: 'am_fenrir', label: 'Fenrir' },
      { id: 'am_liam', label: 'Liam' },
      { id: 'am_michael', label: 'Michael' },
      { id: 'am_onyx', label: 'Onyx' },
      { id: 'am_puck', label: 'Puck' },
      { id: 'am_santa', label: 'Santa' },
    ],
  },
  {
    title: 'British female',
    voices: [
      { id: 'bf_alice', label: 'Alice' },
      { id: 'bf_emma', label: 'Emma' },
      { id: 'bf_isabella', label: 'Isabella' },
      { id: 'bf_lily', label: 'Lily' },
    ],
  },
  {
    title: 'British male',
    voices: [
      { id: 'bm_daniel', label: 'Daniel' },
      { id: 'bm_fable', label: 'Fable' },
      { id: 'bm_george', label: 'George' },
      { id: 'bm_lewis', label: 'Lewis' },
    ],
  },
]
const ALL_VOICES = VOICE_GROUPS.flatMap(group => group.voices.map(voice => voice.id))

export function Generation({ store, form }: SectionProps) {
  return (
    <>
      <Group title="AI model">
        <DividerRow last label="Claude" hint="Model for meanings, phrase polish and topic words.">
          <Segmented value={form.ai_model} options={AI_MODELS} onChange={model => store.setField('ai_model', model)} />
        </DividerRow>
      </Group>
      <Speech store={store} form={form} />
      <Group title="Pictures">
        <Pictures store={store} form={form} />
      </Group>
    </>
  )
}

function Speech({ store, form }: SectionProps) {
  const speed = form.tts_speed ?? TTS_SPEED.fallback
  const enabled = form.tts_enabled_voices ?? ALL_VOICES
  const toggle = (id: string) => store.setField('tts_enabled_voices', enabled.includes(id) ? enabled.filter(v => v !== id) : [...enabled, id])
  return (
    <Group title="Text-to-speech">
      <DividerRow label="Speed">
        <Text tone="muted" size="s">{speed.toFixed(1)}×</Text>
        <Range min={TTS_SPEED.min} max={TTS_SPEED.max} step={TTS_SPEED.step} value={speed} onChange={e => store.setField('tts_speed', parseFloat(e.target.value))} />
      </DividerRow>
      <DividerRow last label="Voices" hint="Each phrase is read by a random voice from the selected ones." />
      <div className={css.voices}>
        {VOICE_GROUPS.map(group => (
          <div key={group.title} className={css.voiceGroup}>
            <span className={css.voiceTitle}>{group.title}</span>
            <div className={css.chips}>
              {group.voices.map(voice => (
                <Chip key={voice.id} outlined on={enabled.includes(voice.id)} onClick={() => toggle(voice.id)}>
                  {voice.label}
                </Chip>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Group>
  )
}

function Pictures({ store, form }: SectionProps) {
  const count = form.images_per_source ?? IMAGES_PER_SOURCE.fallback
  return (
    <DividerRow last label="Pictures per source" hint="How many pictures each source offers when you look for a picture of a word.">
      <Text tone="muted" size="s">{count}</Text>
      <Range min={IMAGES_PER_SOURCE.min} max={IMAGES_PER_SOURCE.max} step={IMAGES_PER_SOURCE.step} value={count} onChange={e => store.setField('images_per_source', parseInt(e.target.value, 10))} />
    </DividerRow>
  )
}
