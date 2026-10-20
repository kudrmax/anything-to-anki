import type { SourceStatus } from '@/api/types'
import { Button } from '@/ui'
import { PROCESS_LABEL } from './processOffer'

interface ReviewActionProps {
  /** Статус набора, как его отдал backend: источника, коллекции или всех. */
  status: SourceStatus
  /** Набор открывается на ревью — решает backend. */
  canReview: boolean
  /** Главное действие экрана: кнопка ревью залита. */
  primary: boolean
  onProcess: () => void
  onReview: () => void
}

/** Одна кнопка для строки источника и шапки коллекции: обработать или открыть ревью набора. */
export function ReviewAction({ status, canReview, primary, onProcess, onReview }: ReviewActionProps) {
  const processLabel = PROCESS_LABEL[status]
  if (processLabel !== undefined) return <Button onClick={onProcess}>{processLabel}</Button>
  if (!canReview) return null
  const reviewVariant = primary ? 'fill' : 'soft'
  if (status === 'done') return <Button variant={reviewVariant} onClick={onReview}>Review</Button>
  if (status === 'partially_reviewed') return <Button variant={reviewVariant} onClick={onReview}>Continue</Button>
  if (status === 'reviewed') return <Button variant="link" onClick={onReview}>Open</Button>
  return null
}
