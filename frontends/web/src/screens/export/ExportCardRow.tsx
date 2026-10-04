import { useState, type MouseEvent } from 'react'
import { Sparkles } from 'lucide-react'
import type { CardPreview } from '@/api/types'
import type { AudioPlayer } from '@/lib/useAudioPlayer'
import { nonEmptyLines, stripMarkdown } from '@/lib/text/meaning'
import { Button, Icon, IconButton, MediaThumb, Text } from '@/ui'
import phrase from '@/ui/phrase.module.css'
import css from './export.module.css'

/** Backend отдаёт значение готовым HTML: определение, затем пояснения через <br>. */
const PARAGRAPH_BREAK = /<br\s*\/?>/i

interface ExportCardRowProps {
  card: CardPreview
  /** В группе есть карточки с видео: колонка превью нужна всем строкам. */
  withMedia: boolean
  generating: boolean
  onGenerate: (candidateId: number) => void
  player: AudioPlayer
}

const stop = (e: MouseEvent) => e.stopPropagation()

export function ExportCardRow({ card, withMedia, generating, onGenerate, player }: ExportCardRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [definition, ...details] = card.meaning ? card.meaning.split(PARAGRAPH_BREAK) : []
  const examples = card.examples ? nonEmptyLines(card.examples).map(stripMarkdown) : []
  const classes = [css.row, withMedia && css.withMedia].filter(Boolean).join(' ')

  return (
    <div className={classes} onClick={() => setExpanded(open => !open)}>
      <div className={css.main}>
        {/* sentence и meaning приходят из backend готовым HTML с выделенным словом */}
        <p className={`${css.sentence} ${phrase.html}`} dangerouslySetInnerHTML={{ __html: card.sentence }} />
        {definition
          ? <p className={css.definition} dangerouslySetInnerHTML={{ __html: definition }} />
          : <p className={css.missing}>No meaning yet — generate it before export</p>}
        {expanded && (
          <div className={css.details}>
            {details.map((paragraph, i) => <p key={i} dangerouslySetInnerHTML={{ __html: paragraph }} />)}
            {card.synonyms && <p>{card.synonyms}</p>}
            {card.ipa && <Text mono>{card.ipa}</Text>}
            {examples.length > 0 && (
              <ul className={css.examples}>
                {examples.map((line, i) => <li key={i}>{line}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
      <div className={css.translation} onClick={stop}>
        {card.meaning
          ? card.translation
          : (
            <Button variant="accent-link" busy={generating} onClick={() => onGenerate(card.candidate_id)}>
              <Icon as={Sparkles} size="s" />Generate
            </Button>
          )}
      </div>
      {withMedia && (
        <div className={css.media} onClick={stop}>
          <MediaThumb
            screenshotUrl={card.screenshot_url}
            audioUrl={card.audio_url}
            playing={player.playingUrl === card.audio_url}
            onToggle={player.toggle}
          />
        </div>
      )}
      <div className={css.more} onClick={stop}>
        {card.meaning && <IconButton icon={Sparkles} label="Regenerate meaning" busy={generating} onClick={() => onGenerate(card.candidate_id)} />}
      </div>
    </div>
  )
}
