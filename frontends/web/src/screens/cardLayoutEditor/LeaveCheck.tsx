import type { CardElement } from '@/api/types'
import { Button, Modal } from '@/ui'
import { ELEMENT_LABEL } from './labels'
import css from './cardLayoutEditor.module.css'

interface LeaveCheckProps {
  hidden: CardElement[]
  onStay: () => void
  onLeave: () => void
}

/** По умолчанию на карточке всё: уйти, оставив блоки скрытыми, можно только явно. */
export function LeaveCheck({ hidden, onStay, onLeave }: LeaveCheckProps) {
  return (
    <Modal
      title="Some blocks are not on the card"
      onClose={onStay}
      footer={(
        <>
          <Button onClick={onStay}>Back to editing</Button>
          <Button variant="fill" onClick={onLeave}>Yes, I did it on purpose</Button>
        </>
      )}
    >
      <p className={css.hint}>These blocks will not show on any card:</p>
      <ul className={css.leaveList}>
        {hidden.map(element => <li key={element}>{ELEMENT_LABEL[element]}</li>)}
      </ul>
    </Modal>
  )
}
