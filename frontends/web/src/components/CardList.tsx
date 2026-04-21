import { useCallback, useState } from 'react'
import { BookOpen, Languages, Loader2, Sparkles, Volume2 } from 'lucide-react'
import { ToolbarButton } from '@/components/CandidateCardV2'
import { MediaThumbnail } from '@/components/MediaThumbnail'
import type { CardPreview } from '@/api/types'

interface CardListProps {
  cards: CardPreview[]
  generatingIds: Set<number>
  onGenerate: (candidateId: number) => void
}

export function CardList({ cards, generatingIds, onGenerate }: CardListProps) {
  return (
    <div className="flex flex-col gap-3">
      {cards.map((card) => (
        <CardPreviewItem
          key={card.candidate_id}
          card={card}
          isGenerating={generatingIds.has(card.candidate_id)}
          onGenerate={() => onGenerate(card.candidate_id)}
        />
      ))}
    </div>
  )
}

interface CardPreviewItemProps {
  card: CardPreview
  isGenerating: boolean
  onGenerate: () => void
}

function CardPreviewItem({ card, isGenerating, onGenerate }: CardPreviewItemProps) {
  const [audioPlaying, setAudioPlaying] = useState(false)

  const handlePlayAudio = useCallback(() => {
    if (!card.audio_url) return
    const audio = new Audio(card.audio_url)
    setAudioPlaying(true)
    audio.onended = () => setAudioPlaying(false)
    audio.onerror = () => setAudioPlaying(false)
    void audio.play()
  }, [card.audio_url])

  return (
    <div className="glass-card rounded-xl p-4 flex flex-col gap-2" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 1 }}>
        <ToolbarButton
          onClick={onGenerate}
          disabled={isGenerating}
          title="Generate meaning with AI"
          ariaLabel="Generate meaning with AI"
        >
          {isGenerating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
        </ToolbarButton>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        {(card.screenshot_url || card.audio_url) && (
          <div style={{ flexShrink: 0, width: '160px' }}>
            <MediaThumbnail
              screenshotUrl={card.screenshot_url}
              audioUrl={card.audio_url}
              isAudioPlaying={audioPlaying}
              onPlayAudio={handlePlayAudio}
              alt={`Screenshot for ${card.lemma}`}
            />
          </div>
        )}

        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <p
            className="text-sm leading-relaxed"
            style={{ color: 'var(--tm)' }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: card.sentence }}
          />

          {card.meaning ? (
            <p
              className="text-xs"
              style={{ color: 'var(--tm)', marginTop: '4px' }}
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: card.meaning }}
            />
          ) : (
            <p className="text-xs italic" style={{ color: 'var(--td)' }}>No definition available</p>
          )}

          {card.translation && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <Languages size={14} style={{ marginTop: '2px', flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ color: 'var(--tm)' }}>{card.translation}</span>
            </div>
          )}

          {card.synonyms && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <BookOpen size={14} style={{ marginTop: '2px', flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ color: 'var(--tm)' }}>{card.synonyms}</span>
            </div>
          )}

          {card.ipa && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <Volume2 size={13} style={{ flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '13px', color: 'var(--tm)' }}>{card.ipa}</span>
            </div>
          )}

          {card.examples && (
            <div
              style={{
                marginTop: '6px',
                padding: '8px 12px',
                background: 'var(--glass)',
                borderRadius: '8px',
                border: '1px solid var(--glass-b)',
              }}
            >
              {card.examples
                .split(/\n+/)
                .filter((l) => l.trim().length > 0)
                .map((line, i) => (
                  <p
                    key={i}
                    style={{
                      margin: i === 0 ? 0 : '4px 0 0',
                      fontSize: '12px',
                      lineHeight: 1.5,
                      color: 'var(--tm)',
                    }}
                  >
                    {line}
                  </p>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
