import type { NoteTypeCheck, NoteTypeKind, Settings } from '@/api/types'
import { Button, DividerRow, Field, Text } from '@/ui'
import type { SettingsStore, TemplatePart } from '../useSettings'
import css from '../settings.module.css'
import { Group } from './Group'
import type { SectionProps } from './types'

const FIELD_MAPPING: { key: keyof Settings; label: string }[] = [
  { key: 'anki_field_sentence', label: 'Sentence' },
  { key: 'anki_field_target_word', label: 'Target word' },
  { key: 'anki_field_meaning', label: 'Meaning' },
  { key: 'anki_field_ipa', label: 'IPA' },
  { key: 'anki_field_image', label: 'Video frame' },
  { key: 'anki_field_meaning_image', label: 'Meaning image' },
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
  { part: 'cloze_front', label: 'Copy Cloze Front' },
  { part: 'cloze_back', label: 'Copy Cloze Back' },
  { part: 'css', label: 'Copy CSS' },
]
const NOTE_TYPE_KIND_LABEL: Record<NoteTypeKind, string> = {
  recognition: 'Note type for regular cards',
  cloze: 'Note type for cloze cards',
}
const NOTE_TYPE_FIX_LABEL: Record<NonNullable<NoteTypeCheck['fix']>, string> = {
  create: 'Create note type',
  add_fields: 'Add missing fields',
}

export function Anki({ store, form }: SectionProps) {
  const text = (key: keyof Settings) => form[key] as string
  return (
    <>
      <Group>
        <DividerRow label="Deck name">
          <div className={css.control}><Field value={form.anki_deck_name} onChange={e => store.setField('anki_deck_name', e.target.value)} /></div>
        </DividerRow>
        <DividerRow label="Note type" hint="«AnythingToAnkiType» is created automatically. Use your own type for custom fields.">
          <div className={css.control}><Field value={form.anki_note_type} onChange={e => store.setField('anki_note_type', e.target.value)} /></div>
        </DividerRow>
        <DividerRow last label="Cloze note type" hint="«AnythingToAnkiCloze» is created automatically. Your own type must be a cloze type with the same fields.">
          <div className={css.control}><Field value={form.anki_cloze_note_type} onChange={e => store.setField('anki_cloze_note_type', e.target.value)} /></div>
        </DividerRow>
      </Group>
      <NoteTypesInAnki store={store} />
      <Group title="Field mapping" hint="Which Anki field each part of the card goes to.">
        <div className={css.map}>
          {FIELD_MAPPING.map(({ key, label }) => (
            <label key={key}>
              <span>{label}</span>
              <Field value={text(key)} onChange={e => store.setField(key, e.target.value)} />
            </label>
          ))}
        </div>
      </Group>
      <Group title="Card template" hint="Copy and paste into Anki's card template editor. Field names match your mapping above.">
        <div className={css.actions}>
          {TEMPLATE_PARTS.map(({ part, label }) => (
            <Button key={part} onClick={() => void store.copyTemplate(part)}>
              {store.copiedTemplate === part ? 'Copied' : label}
            </Button>
          ))}
        </div>
      </Group>
    </>
  )
}

function NoteTypesInAnki({ store }: { store: SettingsStore }) {
  const types = store.noteTypes ?? []
  return (
    <Group title="In Anki" hint="Both note types as they are in the running Anki.">
      {store.noteTypesError && <DividerRow last label={<Text tone="err">{store.noteTypesError}</Text>} />}
      {types.map((t, index) => (
        <DividerRow
          key={t.kind}
          last={index === types.length - 1}
          label={`«${t.note_type}»`}
          hint={
            t.fix === null ? NOTE_TYPE_KIND_LABEL[t.kind]
              : t.fix === 'create' ? <Text tone="err">Not in Anki</Text>
                : <Text tone="err">Missing fields: {t.missing_fields.join(', ')}</Text>
          }
        >
          {t.fix === null
            ? <Text tone="ok">✓ Ready</Text>
            : <Button busy={store.fixingNoteType === t.kind} onClick={() => void store.fixNoteType(t.kind)}>{NOTE_TYPE_FIX_LABEL[t.fix]}</Button>}
        </DividerRow>
      ))}
    </Group>
  )
}
