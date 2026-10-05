import type { MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CardPreview, MissingCardPart } from '@/api/types'
import type { AudioPlayer } from '@/lib/useAudioPlayer'
import { Badge, MediaThumb } from '@/ui'
import phrase from '@/ui/phrase.module.css'
import css from './export.module.css'

/** Backend отдаёт значение готовым HTML: определение, затем пояснения через <br>. */
const PARAGRAPH_BREAK = /<br\s*\/?>/i

const MISSING_LABEL: Record<MissingCardPart, string> = { meaning: 'No meaning', audio: 'No audio' }

interface ExportCardRowProps {
  card: CardPreview
  sourceId: number
  /** В группе есть карточки с видео: колонка превью нужна всем строкам. */
  withMedia: boolean
  player: AudioPlayer
}

const stop = (e: MouseEvent) => e.stopPropagation()

/** Строка карточки: клик открывает её на ревью, где карточку можно дополнить. */
export function ExportCardRow({ card, sourceId, withMedia, player }: ExportCardRowProps) {
  const navigate = useNavigate()
  const [definition] = card.meaning ? card.meaning.split(PARAGRAPH_BREAK) : []
  const classes = [css.row, withMedia && css.withMedia].filter(Boolean).join(' ')

  return (
    <div className={classes} onClick={() => navigate(`/sources/${sourceId}/review?candidate=${card.candidate_id}`)}>
      <div className={css.main}>
        {/* sentence и meaning приходят из backend готовым HTML с выделенным словом */}
        <div className={css.sentenceRow}>
          <p className={`${css.sentence} ${phrase.html}`} dangerouslySetInnerHTML={{ __html: card.sentence }} />
          {card.is_cloze && <Badge>cloze</Badge>}
        </div>
        {definition && <p className={css.definition} dangerouslySetInnerHTML={{ __html: definition }} />}
        {card.missing.length > 0 && (
          <p className={css.missing}>{card.missing.map(part => MISSING_LABEL[part]).join(' · ')}</p>
        )}
      </div>
      <div className={css.translation}>{card.translation}</div>
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
    </div>
  )
}
