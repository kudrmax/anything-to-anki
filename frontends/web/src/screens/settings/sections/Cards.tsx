import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CLOZE_DEFAULT_HINT_OPTIONS } from '@/lib/clozeHints'
import { autoPlayAudioPref } from '@/lib/preferences'
import { CARD_LAYOUT_PATH } from '@/screens/cardLayoutEditor/paths'
import { Button, Chip, DividerRow, Field, Range, Segmented, Switch, Text } from '@/ui'
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

export function Cards({ store, form }: SectionProps) {
  return (
    <>
      <ReviewScreen store={store} form={form} />
      <GeneratedContent store={store} form={form} />
    </>
  )
}

/** Как карточка выглядит и ведёт себя на экране ревью; в Anki это не уходит. */
function ReviewScreen({ store, form }: SectionProps) {
  const navigate = useNavigate()
  const [autoPlay, setAutoPlay] = useState<boolean>(() => autoPlayAudioPref.read())
  const toggleAutoPlay = (next: boolean) => { setAutoPlay(next); autoPlayAudioPref.write(next) }
  return (
    <Group title="Review screen">
      <DividerRow label="Card layout" hint="Which parts the review card shows and where. You arrange them on a sample card.">
        <Button onClick={() => navigate(CARD_LAYOUT_PATH)}>Open the editor</Button>
      </DividerRow>
      <DividerRow label="Auto-play audio" hint="Plays the card's audio when it opens. Saved in this browser only.">
        <Switch checked={autoPlay} onChange={toggleAutoPlay} label="Auto-play audio" />
      </DividerRow>
      <DividerRow label="Default cloze hint" hint="Preselected when you mark a phrase as Cloze. You can change it on any card.">
        <Segmented
          value={form.cloze_default_hint}
          options={CLOZE_DEFAULT_HINT_OPTIONS}
          onChange={hint => store.change('cloze_default_hint', hint)}
        />
      </DividerRow>
      <DividerRow last label="Generate next" hint="How many cards «Generate next» in the ✨ menu takes, from the top of the list.">
        <div className={css.number}>
          <Field
            type="number"
            min={1}
            step={1}
            value={Number.isNaN(form.generation_batch_size) ? '' : form.generation_batch_size}
            onChange={e => store.edit('generation_batch_size', e.target.valueAsNumber)}
            onBlur={() => void store.commit()}
            onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }}
          />
        </div>
      </DividerRow>
    </Group>
  )
}

/** Что генерируется для карточки: это видно и на ревью, и в Anki. */
function GeneratedContent({ store, form }: SectionProps) {
  const speed = form.tts_speed ?? TTS_SPEED.fallback
  const enabled = form.tts_enabled_voices ?? ALL_VOICES
  const toggle = (id: string) => store.change('tts_enabled_voices', enabled.includes(id) ? enabled.filter(v => v !== id) : [...enabled, id])
  return (
    <Group title="Generated content">
      <DividerRow label="AI model" hint="Writes meanings, polishes phrases and picks topic words. Opus gives the best results and uses the most of your plan.">
        <Segmented value={form.ai_model} options={AI_MODELS} onChange={model => store.change('ai_model', model)} />
      </DividerRow>
      <DividerRow label="Speech speed" hint="Text-to-speech of the phrase. Applies to audio made after the change.">
        <Text tone="muted" size="s">{speed.toFixed(1)}×</Text>
        <Range min={TTS_SPEED.min} max={TTS_SPEED.max} step={TTS_SPEED.step} value={speed} onChange={e => store.change('tts_speed', parseFloat(e.target.value))} />
      </DividerRow>
      <DividerRow last label="Voices" hint="Each phrase gets a random voice from the selected ones. Applies to audio made after the change." />
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
      <Pictures store={store} form={form} />
    </Group>
  )
}

function Pictures({ store, form }: SectionProps) {
  const count = form.images_per_source ?? IMAGES_PER_SOURCE.fallback
  return (
    <DividerRow last label="Pictures per site" hint="How many pictures Wiktionary, Bing and Yandex each offer when you pick a picture for a word.">
      <Text tone="muted" size="s">{count}</Text>
      <Range min={IMAGES_PER_SOURCE.min} max={IMAGES_PER_SOURCE.max} step={IMAGES_PER_SOURCE.step} value={count} onChange={e => store.change('images_per_source', parseInt(e.target.value, 10))} />
    </DividerRow>
  )
}
