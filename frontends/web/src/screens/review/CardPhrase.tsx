import type { KeyboardEvent } from 'react'
import type { StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import type { PhraseEditor } from './usePhraseEditor'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface CardPhraseProps {
  candidate: StoredCandidate
  editor: PhraseEditor
}

/** Фраза карточки, а в режиме правки — поле: Enter сохраняет, Esc отменяет. */
export function CardPhrase({ candidate, editor }: CardPhraseProps) {
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

  return (
    <p className={css.phrase} title="Double-click to edit" onDoubleClick={editor.start}>
      {highlightParts(candidate.phrase, candidate.lemma, candidate.surface_form).map((part, i) =>
        part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text,
      )}
    </p>
  )
}
