import { useState } from 'react'
import { Target, Volume2 } from 'lucide-react'
import type { EnrichmentStatus, StoredCandidate } from '@/api/types'
import { FREQ_BAND_LABEL, isDivider, meaningParts, mediaUrl, nonEmptyLines, primaryUsageGroup } from '@/lib/text/meaning'
import { Button, Chip, Icon, MediaThumb, Spinner, Text } from '@/ui'
import { CefrTooltip } from './CefrTooltip'
import { PhraseActions } from './PhraseActions'
import type { Review } from './useReview'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface PhraseDetailsProps {
  candidate: StoredCandidate
  review: Review
}

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

export function PhraseDetails({ candidate, review }: PhraseDetailsProps) {
  const [cefrAnchor, setCefrAnchor] = useState<HTMLElement | null>(null)
  const { sourceId, player } = review
  const meaning = candidate.meaning
  const media = review.mediaFor(candidate)

  const usUrl = mediaUrl(sourceId, candidate.pronunciation?.us_audio_path)
  const ukUrl = mediaUrl(sourceId, candidate.pronunciation?.uk_audio_path)
  const ttsUrl = mediaUrl(sourceId, candidate.tts?.audio_path)
  const hasPronunciationAudio = Boolean(usUrl || ukUrl)

  const usage = primaryUsageGroup(candidate.usage_distribution)
  const frequency = candidate.frequency_band ? FREQ_BAND_LABEL[candidate.frequency_band] : null
  const facts = [usage, frequency].filter((fact): fact is string => Boolean(fact))

  const audioChip = (label: string, url: string | null, title: string) => url && (
    <Chip small on={player.playingUrl === url} title={title} onClick={() => player.toggle(url)}>
      <Icon as={Volume2} size="s" />{label}
    </Chip>
  )

  const paragraphs = meaning?.meaning ? nonEmptyLines(meaning.meaning) : []
  const examples = meaning?.examples ? nonEmptyLines(meaning.examples) : []

  return (
    <div className={css.details}>
      <div className={css.meta}>
        {facts.map(fact => <span key={fact}>{fact}</span>)}
        {candidate.is_phrasal_verb ? <span>phrasal</span> : candidate.cefr_level && (
          <span
            className={css.cefr}
            onMouseEnter={e => candidate.cefr_breakdown && setCefrAnchor(e.currentTarget)}
            onMouseLeave={() => setCefrAnchor(null)}
          >
            {candidate.is_sweet_spot && <Icon as={Target} size="s" />}
            {candidate.cefr_level}
          </span>
        )}
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
      </div>

      <div className={css.body}>
        <div className={css.text}>
          {paragraphs.map((paragraph, i) => isDivider(paragraph)
            ? <hr key={i} className={phrase.divider} />
            : <p key={i} className={i === 0 ? phrase.definition : phrase.context}><RichText text={paragraph} candidate={candidate} /></p>)}
          {paragraphs.length === 0 && (
            isActive(meaning?.status)
              ? <StatusText status={meaning?.status} error={meaning?.error} labels={{ running: 'Generating...', queued: 'Queued', failed: 'Failed to generate' }} />
              : <Button variant="accent-link" busy={review.busy.generating.has(candidate.id)} onClick={() => void review.generate(candidate.id)}>Generate meaning</Button>
          )}
          {(meaning?.translation || meaning?.synonyms) && (
            <p className={phrase.translation}>
              {[meaning.translation, meaning.synonyms].filter(Boolean).join(' · ')}
            </p>
          )}
          {examples.length > 0 && (
            <ul className={phrase.examples}>
              {examples.map((line, i) => <li key={i}><RichText text={line} candidate={candidate} /></li>)}
            </ul>
          )}
        </div>
        <MediaThumb
          screenshotUrl={media.screenshotUrl}
          audioUrl={media.audioUrl}
          status={isActive(candidate.media?.status) ? candidate.media?.status : undefined}
          error={candidate.media?.error}
          playing={player.playingUrl === media.audioUrl}
          onToggle={player.toggle}
        />
      </div>

      <PhraseActions candidate={candidate} review={review} />

      {cefrAnchor && candidate.cefr_breakdown && candidate.cefr_level && (
        <CefrTooltip breakdown={candidate.cefr_breakdown} cefrLevel={candidate.cefr_level} anchor={cefrAnchor} onClose={() => setCefrAnchor(null)} />
      )}
    </div>
  )
}
