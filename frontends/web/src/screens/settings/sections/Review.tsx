import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CLOZE_DEFAULT_HINT_OPTIONS } from '@/lib/clozeHints'
import { autoPlayAudioPref } from '@/lib/preferences'
import { Button, DividerRow, Segmented, Switch } from '@/ui'
import { CARD_LAYOUT_PATH } from '@/screens/cardLayoutEditor/paths'
import { Group } from './Group'
import type { SectionProps } from './types'

export function Review({ store, form }: SectionProps) {
  const navigate = useNavigate()
  const [autoPlay, setAutoPlay] = useState<boolean>(() => autoPlayAudioPref.read())
  const toggle = (next: boolean) => { setAutoPlay(next); autoPlayAudioPref.write(next) }
  return (
    <Group>
      <DividerRow label="Auto-play audio" hint="Play the card's audio when it opens (if available).">
        <Switch checked={autoPlay} onChange={toggle} label="Auto-play audio" />
      </DividerRow>
      <DividerRow label="Default cloze hint" hint="Preselected when you mark a phrase as Cloze. You can change it on any card.">
        <Segmented
          value={form.cloze_default_hint}
          options={CLOZE_DEFAULT_HINT_OPTIONS}
          onChange={hint => store.setField('cloze_default_hint', hint)}
        />
      </DividerRow>
      <DividerRow last label="Card layout" hint="Arrange the review card on the review screen itself, with a sample card.">
        <Button onClick={() => navigate(CARD_LAYOUT_PATH)}>Open the editor</Button>
      </DividerRow>
    </Group>
  )
}
