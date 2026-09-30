import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import type { CardPreview } from '@/api/types'
import type { AudioPlayer } from '@/lib/useAudioPlayer'
import { nonEmptyLines, stripMarkdown } from '@/lib/text/meaning'
import { Button, Icon, IconButton, MediaThumb, Row, Text } from '@/ui'
import phrase from '@/ui/phrase.module.css'

/** Backend отдаёт значение готовым HTML: определение, затем пояснения через <br>. */
const PARAGRAPH_BREAK = /<br\s*\/?>/i

interface ExportCardRowProps {
  card: CardPreview
  generating: boolean
  onGenerate: (candidateId: number) => void
  player: AudioPlayer
}

export function ExportCardRow({ card, generating, onGenerate, player }: ExportCardRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [definition, ...details] = card.meaning ? card.meaning.split(PARAGRAPH_BREAK) : []
  const facts = [card.translation, card.synonyms].filter((fact): fact is string => Boolean(fact))
  const examples = card.examples ? nonEmptyLines(card.examples).map(stripMarkdown) : []

  return (
    <Row
      tone={card.meaning ? 'ok' : 'warn'}
      // sentence и meaning приходят из backend готовым HTML с выделенным словом
      title={<span className={phrase.html} dangerouslySetInnerHTML={{ __html: card.sentence }} />}
      onClick={() => setExpanded(open => !open)}
      actions={card.meaning && <IconButton icon={Sparkles} label="Regenerate meaning" busy={generating} onClick={() => onGenerate(card.candidate_id)} />}
      trailing={
        <>
          {!card.meaning && (
            <Button variant="accent-link" busy={generating} onClick={() => onGenerate(card.candidate_id)}>
              <Icon as={Sparkles} size="s" />Generate
            </Button>
          )}
          <MediaThumb
            screenshotUrl={card.screenshot_url}
            audioUrl={card.audio_url}
            playing={player.playingUrl === card.audio_url}
            onToggle={player.toggle}
          />
        </>
      }
    >
      {definition
        ? <p className={phrase.brief} dangerouslySetInnerHTML={{ __html: definition }} />
        : <p className={phrase.warning}>No meaning yet — generate it before export</p>}
      {(facts.length > 0 || card.ipa) && (
        <p className={phrase.note}>
          {facts.join(' · ')}
          {facts.length > 0 && card.ipa && ' · '}
          {card.ipa && <Text mono>{card.ipa}</Text>}
        </p>
      )}
      {expanded && details.map((paragraph, i) => <p key={i} className={phrase.brief} dangerouslySetInnerHTML={{ __html: paragraph }} />)}
      {expanded && examples.length > 0 && (
        <ul className={phrase.examples}>
          {examples.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
      )}
    </Row>
  )
}
