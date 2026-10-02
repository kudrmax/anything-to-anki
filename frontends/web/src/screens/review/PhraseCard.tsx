import { useState } from 'react'
import { Target, Volume2 } from 'lucide-react'
import type { EnrichmentStatus, PhraseOrigin, StoredCandidate } from '@/api/types'
import { FREQ_BAND_LABEL, highlightParts, isDivider, meaningAction, meaningParts, mediaUrl, nonEmptyLines, primaryUsageGroup } from '@/lib/text/meaning'
import { Button, Chip, Icon, MediaThumb, Spinner, Text } from '@/ui'
import { CefrTooltip } from './CefrTooltip'
import { DecisionButtons, PhraseTools } from './PhraseActions'
import type { Review } from './useReview'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface PhraseCardProps {
  candidate: StoredCandidate
  review: Review
}

const GENERATED_PHRASE = 'generated phrase'

/** Откуда фраза кандидата темы: из другого источника или сгенерирована. */
const originLabel = (origin: PhraseOrigin): string =>
  origin.kind === 'source' && origin.source_title ? `from ${origin.source_title}` : GENERATED_PHRASE

const isActive = (status: EnrichmentStatus | undefined): boolean => status === 'queued' || status === 'running' || status === 'failed'

function RichText({ text, candidate }: { text: string; candidate: StoredCandidate }) {
  return (
    <>
      {meaningParts(text, candidate.lemma, candidate.surface_form).map((part, i) =>
        part.target || part.bold ? <b key={i}>{part.text}</b> : part.text,
      )}
    </>
  )
}

function StatusText({ status, labels, error }: { status: EnrichmentStatus | undefined; labels: Partial<Record<EnrichmentStatus, string>>; error?: string | null }) {
  if (!status || !labels[status]) return null
  return (
    <span className={css.status} title={error ?? undefined}>
      {status === 'running' && <Spinner />}
      <Text tone={status === 'failed' ? 'err' : 'muted'} size="s">{labels[status]}</Text>
    </span>
  )
}

/** Текущая фраза: слева то, что запоминаешь, справа то, что объясняет. */
export function PhraseCard({ candidate, review }: PhraseCardProps) {
  const [cefrAnchor, setCefrAnchor] = useState<HTMLElement | null>(null)
  const { sourceId, player } = review
  const meaning = candidate.meaning
  const media = review.mediaFor(candidate)

  const usUrl = mediaUrl(sourceId, candidate.pronunciation?.us_audio_path)
  const ukUrl = mediaUrl(sourceId, candidate.pronunciation?.uk_audio_path)
  const ttsUrl = mediaUrl(sourceId, candidate.tts?.audio_path)
  const hasPronunciationAudio = Boolean(usUrl || ukUrl)

  const usage = primaryUsageGroup(candidate.usage_distribution)
  const frequency = candidate.frequency_band ? FREQ_BAND_LABEL[candidate.frequency_band]?.toLowerCase() : null
  const facts = [frequency, usage].filter((fact): fact is string => Boolean(fact))

  const audioChip = (label: string, url: string | null, title: string) => url && (
    <Chip small on={player.playingUrl === url} title={title} onClick={() => player.toggle(url)}>
      <Icon as={Volume2} size="s" />{label}
    </Chip>
  )

  const action = meaningAction(meaning)
  const hasMeta = facts.length > 0 || candidate.is_phrasal_verb || Boolean(candidate.origin) || Boolean(candidate.cefr_level || meaning?.ipa || usUrl || ukUrl || ttsUrl)
    || isActive(candidate.pronunciation?.status) || isActive(candidate.tts?.status)
  const paragraphs = meaning?.meaning ? nonEmptyLines(meaning.meaning) : []
  const examples = meaning?.examples ? nonEmptyLines(meaning.examples) : []
  const [definition, ...context] = paragraphs

  return (
    <article className={css.card} data-candidate-id={candidate.id}>
      <div className={css.cardLeft}>
        <p className={css.phrase}>
          {highlightParts(candidate.context_fragment, candidate.lemma, candidate.surface_form).map((part, i) =>
            part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text,
          )}
        </p>
        {hasMeta && (
          <div className={css.meta}>
            {meaning?.ipa && <Text mono>{meaning.ipa}</Text>}
            {audioChip('US', usUrl, 'Play US pronunciation')}
            {audioChip('UK', ukUrl, 'Play UK pronunciation')}
            {!hasPronunciationAudio && (
              <StatusText status={candidate.pronunciation?.status} error={candidate.pronunciation?.error} labels={{ running: 'Downloading...', queued: 'Queued', failed: 'Failed' }} />
            )}
            {audioChip('TTS', ttsUrl, 'Play TTS audio')}
            {!ttsUrl && (
              <StatusText status={candidate.tts?.status} error={candidate.tts?.error} labels={{ running: 'TTS...', queued: 'TTS queued', failed: 'TTS failed' }} />
            )}
            {candidate.is_phrasal_verb ? <Chip small>phrasal verb</Chip> : candidate.cefr_level && (
              <span
                className={css.cefr}
                onMouseEnter={e => candidate.cefr_breakdown && setCefrAnchor(e.currentTarget)}
                onMouseLeave={() => setCefrAnchor(null)}
              >
                <Chip small>
                  {candidate.is_sweet_spot && <Icon as={Target} size="s" />}
                  {candidate.cefr_level}
                </Chip>
              </span>
            )}
            {facts.map(fact => <span key={fact} className={css.fact}>{fact}</span>)}
            {candidate.origin && <span className={css.fact}>{originLabel(candidate.origin)}</span>}
          </div>
        )}
        {meaning?.translation && <p className={css.translation}>{meaning.translation}</p>}
        {meaning?.synonyms && <p className={css.synonyms}>{meaning.synonyms}</p>}
        <MediaThumb
          screenshotUrl={media.screenshotUrl}
          audioUrl={media.audioUrl}
          status={isActive(candidate.media?.status) ? candidate.media?.status : undefined}
          error={candidate.media?.error}
          playing={player.playingUrl === media.audioUrl}
          onToggle={player.toggle}
        />
        <DecisionButtons candidate={candidate} review={review} />
      </div>

      <div className={css.cardRight}>
        {definition && <p className={css.definition}><RichText text={definition} candidate={candidate} /></p>}
        {paragraphs.length === 0 && (
          <div className={css.status}>
            <StatusText status={meaning?.status} error={meaning?.error} labels={{ running: 'Generating...', queued: 'Queued', failed: 'Failed to generate' }} />
            {action && (
              <Button variant="accent-link" busy={review.busy.generating.has(candidate.id)} onClick={() => void review.generate(candidate.id)}>
                {action === 'retry' ? 'Retry' : 'Generate meaning'}
              </Button>
            )}
          </div>
        )}
        {context.map((paragraph, i) => isDivider(paragraph)
          ? <hr key={i} className={phrase.divider} />
          : <p key={i} className={css.context}><RichText text={paragraph} candidate={candidate} /></p>)}
        {examples.length > 0 && (
          <ul className={css.examples}>
            {examples.map((line, i) => <li key={i}><RichText text={line} candidate={candidate} /></li>)}
          </ul>
        )}
        <PhraseTools candidate={candidate} review={review} />
      </div>

      {cefrAnchor && candidate.cefr_breakdown && candidate.cefr_level && (
        <CefrTooltip breakdown={candidate.cefr_breakdown} cefrLevel={candidate.cefr_level} anchor={cefrAnchor} onClose={() => setCefrAnchor(null)} />
      )}
    </article>
  )
}
