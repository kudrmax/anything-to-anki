import type { UndoOffer } from './useUndo'
import css from './UndoToast.module.css'

export function UndoToast({ offer, onUndo }: { offer: UndoOffer | null; onUndo: () => void }) {
  if (!offer) return null
  return (
    <div className={css.toast} role="status">
      <span>{offer.message}</span>
      <button type="button" className={css.undo} onClick={onUndo}>Undo</button>
    </div>
  )
}
