import type { KeyboardEvent } from 'react'
import type { StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import { clozeParts } from './clozeParts'
import { ClozePhrase } from './ClozePhrase'
import type { ClozeEditor } from './useClozeEditor'
import type { PhraseEditor } from './usePhraseEditor'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface CardPhraseProps {
  candidate: StoredCandidate
  editor: PhraseEditor
  cloze: ClozeEditor
}

/**
 * Фраза карточки, а в режиме правки — поле: Enter сохраняет, Esc отменяет.
 * В режиме разметки cloze слова фразы — кнопки; у cloze-карточки скрытые слова в пунктирной рамке.
 */
export function CardPhrase({ candidate, editor, cloze }: CardPhraseProps) {
  const { draft, saving } = editor

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void editor.save()
    } else if (e.key === 'Escape') {
      e.stopPropagation()
      editor.cancel()
    }
  }

  if (draft !== null) {
    return (
      // Невидимая копия текста в той же ячейке грида растит поле по содержимому.
      <div className={`${css.phrase} ${css.phraseEdit}`} data-value={draft}>
        <textarea
          value={draft}
          autoFocus
          rows={1}
          readOnly={saving}
          aria-label="Edit phrase"
          onFocus={e => e.target.setSelectionRange(e.target.value.length, e.target.value.length)}
          onChange={e => editor.setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => void editor.save()}
        />
      </div>
    )
  }

  if (cloze.active) {
    return cloze.preview && cloze.draft
      ? <ClozePhrase preview={cloze.preview} hidden={cloze.draft.hidden_word_indices} onToggle={cloze.toggleWord} />
      : <p className={css.phrase}>{candidate.phrase}</p>
  }

  const parts = highlightParts(candidate.phrase, candidate.lemma, candidate.surface_form)
  if (candidate.cloze) {
    return (
      <p className={`${css.phrase} ${css.clozeSaved}`} title={candidate.can_cloze ? 'Click to change the hidden words' : undefined} onClick={candidate.can_cloze ? cloze.start : undefined}>
        {clozeParts(parts, candidate.cloze.hidden_word_indices).map((part, i) => {
          if (part.hidden) return <span key={i} className={css.clozeGap}>{part.text}</span>
          return part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text
        })}
      </p>
    )
  }

  return (
    <p className={css.phrase} title="Double-click to edit" onDoubleClick={editor.start}>
      {parts.map((part, i) =>
        part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text,
      )}
    </p>
  )
}
