import { useState, type CSSProperties } from 'react'
import { Brackets, Check } from 'lucide-react'
import type { CandidateCloze, CardLayoutView, DecisionButton, PhraseOrigin, StoredCandidate } from '@/api/types'
import { columnTracks, type CardBlockContext } from '@/cardLayout'
import { CLOZE_HINT_LABEL } from '@/lib/clozeHints'
import { Icon } from '@/ui'
import { CardBody } from './CardBody'
import { CardPhrase } from './CardPhrase'
import { CefrTooltip } from './CefrTooltip'
import { ClozePanel } from './ClozePanel'
import { DecisionButtons, PhraseTools } from './PhraseActions'
import { PictureSuggestions } from './PictureSuggestions'
import type { PictureSuggestionsLoader } from './usePictureSuggestions'
import { audioUrlForCandidate, type Review } from './useReview'
import { useClozeEditor } from './useClozeEditor'
import { usePhraseEditor } from './usePhraseEditor'
import css from './review.module.css'

interface PhraseCardProps {
  candidate: StoredCandidate
  review: Review
  /** Раскладка тела карточки; null — ещё не загрузилась. */
  layout: CardLayoutView | null
  /** Нет — подсказки картинок выключены. */
  suggestPictures: PictureSuggestionsLoader | null
}

const GENERATED_PHRASE = 'generated phrase'
/** Цифры решений видны на кнопках, здесь — только неочевидные клавиши. */
const KEYS_HINT = '↑↓ ←→ phrases · Space learn · ⌘V paste a picture'

/** Подпись нажатой кнопки рядом с фразой; какая нажата, решает backend. */
const DECIDED_LABEL: Record<DecisionButton, string> = { learn: 'Learn', cloze: 'Cloze', known: 'Known', skip: 'Skipped' }

/** Откуда фраза кандидата темы: из другого источника или сгенерирована. */
const originLabel = (origin: PhraseOrigin): string =>
  origin.kind === 'source' && origin.source_title ? `from ${origin.source_title}` : GENERATED_PHRASE

const clozeLabel = ({ hint_kind }: CandidateCloze): string =>
  hint_kind === 'none' ? 'cloze · no hint' : `cloze · hint: ${CLOZE_HINT_LABEL[hint_kind].toLowerCase()}`

/**
 * Текущая фраза: сверху фраза, под ней тело по раскладке пользователя, снизу решения, факты и инструменты.
 */
export function PhraseCard({ candidate, review, layout, suggestPictures }: PhraseCardProps) {
  const [cefrAnchor, setCefrAnchor] = useState<HTMLElement | null>(null)
  // Телефон: справка свёрнута в строку Details.
  const [detailsOpen, setDetailsOpen] = useState(false)
  const phraseEditor = usePhraseEditor(candidate, review)
  const clozeEditor = useClozeEditor(candidate, review)
  // Правка текста и разметка cloze не открываются вместе: индексы скрытых слов относятся к старому тексту.
  const editPhrase = () => {
    clozeEditor.cancel()
    phraseEditor.start()
  }
  const decided = candidate.state.buttons.find(button => button.pressed)?.button ?? null
  const media = review.mediaFor(candidate)

  const ctx: CardBlockContext = {
    candidate,
    media,
    playingUrl: review.player.playingUrl,
    togglePlay: review.player.toggle,
    keyAudioUrl: audioUrlForCandidate(candidate),
    generating: review.busy.generating.has(candidate.phrase_id),
    generate: () => void review.generate(candidate.phrase_id),
    useExample: line => void review.replaceWithExample(candidate.phrase_id, line),
    pictureSuggestions: suggestPictures && <PictureSuggestions candidate={candidate} review={review} load={suggestPictures} />,
    showCefr: setCefrAnchor,
  }

  return (
    <div className={css.cardBlock}>
      <article
        className={clozeEditor.active ? `${css.card} ${css.clozeEditing}` : css.card}
        data-candidate-id={candidate.phrase_id}
        style={{ '--card-cols': layout ? columnTracks(layout.layout.columns) : undefined } as CSSProperties}
      >
        <header className={css.cardHead}>
          <div className={css.phraseRow}>
            <CardPhrase candidate={candidate} editor={phraseEditor} cloze={clozeEditor} />
            {decided && (
              <span className={css.decided}><Icon as={Check} size="s" />{DECIDED_LABEL[decided]}</span>
            )}
          </div>
          {clozeEditor.active && <ClozePanel editor={clozeEditor} />}
        </header>

        {layout && <CardBody view={layout} ctx={ctx} detailsOpen={detailsOpen} onToggleDetails={() => setDetailsOpen(open => !open)} />}

        <footer className={detailsOpen ? css.cardFoot : `${css.cardFoot} ${css.collapsed}`}>
          {/* Десктоп: решения — в нижней полосе карточки; на телефоне они в панели под карточкой. */}
          <div className={css.footDecisions}>
            <DecisionButtons candidate={candidate} review={review} />
          </div>
          {/* Не влезает рядом с решениями — переносится под них. */}
          <div className={css.footRest}>
            <div className={css.facts}>
              {candidate.cloze && (
                <span className={css.clozeFact}><Icon as={Brackets} size="s" />{clozeLabel(candidate.cloze)}</span>
              )}
              {candidate.origin && <span>{originLabel(candidate.origin)}</span>}
            </div>
            <PhraseTools candidate={candidate} review={review} onEditPhrase={editPhrase} />
          </div>
        </footer>

        {cefrAnchor && candidate.cefr_breakdown && candidate.cefr_level && (
          <CefrTooltip breakdown={candidate.cefr_breakdown} cefrLevel={candidate.cefr_level} anchor={cefrAnchor} onClose={() => setCefrAnchor(null)} />
        )}
      </article>
      {/* Клавиши без своей кнопки — под карточкой, а не в ней. */}
      <p className={css.keysHint}>{KEYS_HINT}</p>
    </div>
  )
}
