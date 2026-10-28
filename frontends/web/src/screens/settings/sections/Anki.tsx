import type { NoteTypeCheck, NoteTypeKind } from '@/api/types'
import { Button, DividerRow, Text } from '@/ui'
import type { SettingsStore, TemplatePart } from '../useSettings'
import css from '../settings.module.css'
import { Group } from './Group'
import { SettingField, type TextSetting } from './SettingField'
import type { SectionProps } from './types'

const FIELD_MAPPING: { key: TextSetting; label: string }[] = [
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
const NOTE_TYPE_FIX_LABEL: Record<NonNullable<NoteTypeCheck['fix']>, string> = {
  create: 'Create note type',
  add_fields: 'Add missing fields',
}

export function Anki({ store }: SectionProps) {
  const status = (kind: NoteTypeKind) => store.noteTypes?.find(t => t.kind === kind) ?? null
  return (
    <>
      <Group>
        <DividerRow label="Deck" hint="Cards are added to this deck. It is created if missing.">
          <div className={css.control}><SettingField store={store} name="anki_deck_name" /></div>
        </DividerRow>
        <NoteTypeRow store={store} check={status('recognition')} name="anki_note_type" label="Note type" hint="«AnythingToAnkiType» is created automatically. Use your own type for custom fields." />
        <NoteTypeRow last store={store} check={status('cloze')} name="anki_cloze_note_type" label="Cloze note type" hint="«AnythingToAnkiCloze» is created automatically. Your own type must be a cloze type with the same fields." />
        {store.noteTypesError && <p className={css.groupHint}>Note types can't be checked: {store.noteTypesError}.</p>}
      </Group>
      <Group collapsible title="Fields and templates" hint="Only for your own note type: which field each part of the card goes to, and the card templates.">
        <div className={css.map}>
          {FIELD_MAPPING.map(({ key, label }) => (
            <label key={key}>
              <span>{label}</span>
              <SettingField store={store} name={key} />
            </label>
          ))}
        </div>
        <p className={css.groupHint}>Card templates with these field names, to paste into Anki's template editor:</p>
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

interface NoteTypeRowProps {
  store: SettingsStore
  check: NoteTypeCheck | null
  name: 'anki_note_type' | 'anki_cloze_note_type'
  label: string
  hint: string
  last?: boolean
}

/** Поле note type и его состояние в запущенном Anki: готов или кнопка, которая его чинит. */
function NoteTypeRow({ store, check, name, label, hint, last = false }: NoteTypeRowProps) {
  const problem = check?.fix === 'create' ? 'Not in Anki'
    : check?.fix === 'add_fields' ? `Missing in Anki: ${check.missing_fields.join(', ')}`
      : null
  return (
    <DividerRow last={last} label={label} hint={problem ? <Text tone="err">{problem}</Text> : hint}>
      {check?.fix === null && <Text tone="ok" size="s">✓ In Anki</Text>}
      {check?.fix && (
        <Button busy={store.fixingNoteType === check.kind} onClick={() => void store.fixNoteType(check.kind)}>{NOTE_TYPE_FIX_LABEL[check.fix]}</Button>
      )}
      <div className={css.control}><SettingField store={store} name={name} /></div>
    </DividerRow>
  )
}
