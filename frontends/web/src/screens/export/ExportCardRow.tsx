import { Sparkles } from 'lucide-react'
import type { CardPreview } from '@/api/types'
import type { AudioPlayer } from '@/lib/useAudioPlayer'
import { nonEmptyLines, stripMarkdown } from '@/lib/text/meaning'
import { Button, IconButton, MediaThumb, Row } from '@/ui'
import phrase from '@/ui/phrase.module.css'

interface ExportCardRowProps {
  card: CardPreview
  generating: boolean
  onGenerate: (candidateId: number) => void
  player: AudioPlayer
}

export function ExportCardRow({ card, generating, onGenerate, player }: ExportCardRowProps) {
  const facts = [card.translation, card.synonyms, card.ipa].filter((fact): fact is string => Boolean(fact))
  const examples = card.examples ? nonEmptyLines(card.examples).map(stripMarkdown) : []

  return (
    <Row
      tone={card.meaning ? 'ok' : 'warn'}
      // sentence и meaning приходят из backend готовым HTML с выделенным словом
      title={<span className={phrase.html} dangerouslySetInnerHTML={{ __html: card.sentence }} />}
      actions={card.meaning && <IconButton icon={Sparkles} label="Regenerate meaning" busy={generating} onClick={() => onGenerate(card.candidate_id)} />}
      trailing={
        <>
          {!card.meaning && <Button variant="accent-link" busy={generating} onClick={() => onGenerate(card.candidate_id)}>Generate</Button>}
          <MediaThumb
            screenshotUrl={card.screenshot_url}
            audioUrl={card.audio_url}
            playing={player.playingUrl === card.audio_url}
            onToggle={player.toggle}
          />
        </>
      }
    >
      {card.meaning
        ? <p className={phrase.context} dangerouslySetInnerHTML={{ __html: card.meaning }} />
        : <p className={phrase.note}>No definition available</p>}
      {facts.length > 0 && <p className={phrase.note}>{facts.join(' · ')}</p>}
      {examples.length > 0 && (
        <ul className={phrase.examples}>
          {examples.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
      )}
    </Row>
  )
}
