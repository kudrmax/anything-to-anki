import type { ReactNode } from 'react'
import { Target, Volume2 } from 'lucide-react'
import type { CardElement, EnrichmentStatus, StoredCandidate } from '@/api/types'
import { KEY_LABEL } from '@/lib/hotkeys'
import { FREQ_BAND_LABEL, isDivider, mediaUrl, nonEmptyLines, primaryUsageGroup } from '@/lib/text/meaning'
import { Button, Chip, Icon, Kbd, MediaThumb } from '@/ui'
import type { CardBlockContext } from './CardBlockContext'
import { Examples, RichText, StatusText } from './CardTexts'
import phrase from '@/ui/phrase.module.css'
import css from './cardLayout.module.css'

const isActive = (status: EnrichmentStatus | undefined): boolean => status === 'queued' || status === 'running' || status === 'failed'

/** Линии по краям заметок отделяли их от остального значения; теперь это делает линия раскладки. */
function trimDividers(lines: string[]): string[] {
  let start = 0
  let end = lines.length
  while (start < end && isDivider(lines[start])) start++
  while (end > start && isDivider(lines[end - 1])) end--
  return lines.slice(start, end)
}

/** Строки значения: первая — определение, вторая пересказывает контекст фразы, остальное — заметки. */
function meaningLines(candidate: StoredCandidate) {
  const paragraphs = candidate.meaning?.meaning ? nonEmptyLines(candidate.meaning.meaning) : []
  const [definition, ...rest] = paragraphs
  const context = rest[0] && !isDivider(rest[0]) ? rest[0] : null
  return { paragraphs, definition: definition ?? null, context, notes: trimDividers(context ? rest.slice(1) : rest) }
}

function audioChip(ctx: CardBlockContext, label: string, url: string | null, title: string) {
  return url && (
    <Chip small className={css.textButton} on={ctx.playingUrl === url} title={title} onClick={() => ctx.togglePlay(url)}>
      <Icon as={Volume2} size="s" />{label}{url === ctx.keyAudioUrl && <Kbd>{KEY_LABEL.audio}</Kbd>}
    </Chip>
  )
}

function wordFacts({ candidate, showCefr }: CardBlockContext): ReactNode {
  const usage = primaryUsageGroup(candidate.usage_distribution)
  const frequency = candidate.frequency_band ? FREQ_BAND_LABEL[candidate.frequency_band]?.toLowerCase() : null
  const facts = [frequency, usage].filter((fact): fact is string => Boolean(fact))
  if (!candidate.is_phrasal_verb && !candidate.cefr_level && facts.length === 0) return null
  return (
    <span className={css.wordFacts}>
      {candidate.is_phrasal_verb ? <span>phrasal verb</span> : candidate.cefr_level && (
        <span
          className={css.cefr}
          onMouseEnter={e => candidate.cefr_breakdown && showCefr(e.currentTarget)}
          onMouseLeave={() => showCefr(null)}
        >
          {candidate.is_sweet_spot && <Icon as={Target} size="s" />}
          {candidate.cefr_level}
        </span>
      )}
      {facts.map(fact => <span key={fact}>{fact}</span>)}
    </span>
  )
}

function pronunciation(ctx: CardBlockContext): ReactNode {
  const { candidate } = ctx
  const usUrl = mediaUrl(candidate.source.id, candidate.pronunciation?.us_audio_path)
  const ukUrl = mediaUrl(candidate.source.id, candidate.pronunciation?.uk_audio_path)
  if (!usUrl && !ukUrl && !isActive(candidate.pronunciation?.status)) return null
  return (
    <span className={css.chips}>
      {audioChip(ctx, 'US', usUrl, 'Play US pronunciation')}
      {audioChip(ctx, 'UK', ukUrl, 'Play UK pronunciation')}
      {!usUrl && !ukUrl && (
        <StatusText status={candidate.pronunciation?.status} error={candidate.pronunciation?.error} labels={{ running: 'Downloading...', queued: 'Queued', failed: 'Failed' }} />
      )}
    </span>
  )
}

function tts(ctx: CardBlockContext): ReactNode {
  const { candidate } = ctx
  const url = mediaUrl(candidate.source.id, candidate.tts?.audio_path)
  if (url) return audioChip(ctx, 'TTS', url, 'Play TTS audio')
  if (!isActive(candidate.tts?.status)) return null
  return <StatusText status={candidate.tts?.status} error={candidate.tts?.error} labels={{ running: 'TTS...', queued: 'TTS queued', failed: 'TTS failed' }} />
}

function meaningStatus({ candidate, generating, generate }: CardBlockContext): ReactNode {
  const action = candidate.meaning_action
  if (meaningLines(candidate).paragraphs.length > 0) return null
  if (!isActive(candidate.meaning?.status) && !action) return null
  return (
    <div className={css.status}>
      <StatusText status={candidate.meaning?.status} error={candidate.meaning?.error} labels={{ running: 'Generating...', queued: 'Queued', failed: 'Failed to generate' }} />
      {action && (
        <Button variant="accent-link" className={css.textButton} busy={generating} onClick={generate}>
          {action === 'retry' ? 'Retry' : 'Generate meaning'}
        </Button>
      )}
    </div>
  )
}

function videoFrame({ candidate, media, playingUrl, togglePlay, keyAudioUrl }: CardBlockContext): ReactNode {
  const status = isActive(candidate.media?.status) ? candidate.media?.status : undefined
  if (!media.screenshotUrl && !media.audioUrl && !status) return null
  return (
    <div className={css.dimmed}>
      <MediaThumb
        screenshotUrl={media.screenshotUrl}
        audioUrl={media.audioUrl}
        status={status}
        error={candidate.media?.error}
        playing={playingUrl === media.audioUrl}
        onToggle={togglePlay}
        kbd={media.audioUrl === keyAudioUrl ? KEY_LABEL.audio : undefined}
      />
    </div>
  )
}

function picture({ media }: CardBlockContext): ReactNode {
  return media.meaningImageUrl && (
    <img className={`${css.meaningImage} ${css.dimmed}`} src={media.meaningImageUrl} alt="" onError={e => { e.currentTarget.hidden = true }} />
  )
}

/** Подобранные картинки — только пока своей картинки у карточки нет. */
const pictureChoice = ({ media, pictureSuggestions }: CardBlockContext): ReactNode => !media.meaningImageUrl && pictureSuggestions

function paragraph(className: string, pick: (lines: ReturnType<typeof meaningLines>) => string | null) {
  return ({ candidate }: CardBlockContext): ReactNode => {
    const text = pick(meaningLines(candidate))
    return text && <p className={className}><RichText text={text} candidate={candidate} /></p>
  }
}

/** Что показывает каждый элемент раскладки; null — показывать нечего, блока нет. */
export const CARD_ELEMENTS: Record<CardElement, (ctx: CardBlockContext) => ReactNode> = {
  target: ({ candidate }) => <p className={css.lemma}><b className={`${phrase.target} ${css.lemmaMark}`}>{candidate.lemma}</b></p>,
  translation: ({ candidate }) => candidate.meaning?.translation && <p className={css.translation}>{candidate.meaning.translation}</p>,
  context: paragraph(css.context, lines => lines.context),
  definition: paragraph(css.definition, lines => lines.definition),
  notes: ({ candidate }) => {
    const { notes } = meaningLines(candidate)
    if (notes.length === 0) return null
    return (
      <div className={css.notes}>
        {notes.map((line, i) => isDivider(line)
          ? <hr key={i} className={css.divider} />
          : <p key={i}><RichText text={line} candidate={candidate} /></p>)}
      </div>
    )
  },
  synonyms: ({ candidate }) => candidate.meaning?.synonyms && <p className={css.synonyms}>{candidate.meaning.synonyms}</p>,
  examples: ctx => {
    const lines = ctx.candidate.meaning?.examples ? nonEmptyLines(ctx.candidate.meaning.examples) : []
    return lines.length > 0 && <Examples lines={lines} ctx={ctx} />
  },
  transcription: ({ candidate }) => candidate.meaning?.ipa && <span className={css.transcription}>{candidate.meaning.ipa}</span>,
  pronunciation,
  tts,
  word_facts: wordFacts,
  video_frame: videoFrame,
  picture,
  picture_choice: pictureChoice,
  meaning_status: meaningStatus,
}
