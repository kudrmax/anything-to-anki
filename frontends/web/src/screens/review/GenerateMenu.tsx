import { Sparkles } from 'lucide-react'
import { Button, Icon, Menu, Spinner } from '@/ui'
import { generationItems } from './generationItems'
import type { Review } from './useReview'
import css from './review.module.css'

export function GenerateMenu({ review }: { review: Review }) {
  const { generation } = review
  const items = generationItems(review)

  return (
    <Menu
      items={items}
      emptyText="Loading…"
      trigger={
        <Button variant="link" className={css.iconTrigger} title="Generate phrases, meanings, audio" aria-label="Generate">
          {generation?.in_progress ? <Spinner /> : <Icon as={Sparkles} />}
        </Button>
      }
    />
  )
}
