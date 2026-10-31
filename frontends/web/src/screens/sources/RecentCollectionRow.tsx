import { Ellipsis, Folder } from 'lucide-react'
import type { CollectionNode } from '@/api/types'
import { TOOLTIP_LINE } from '@/lib/text/format'
import { Icon, IconButton, Menu, Progress, Text, type MenuItem } from '@/ui'
import { ReviewAction } from './ReviewAction'
import css from './sources.module.css'

interface RecentCollectionRowProps {
  node: CollectionNode
  /** Имена коллекций над ней, от корня. */
  path: string[]
  processing: boolean
  menuItems: MenuItem[]
  onProcess: () => void
  onReview: () => void
}

const COLLECTION = 'Collection'

/** Коллекция в Recent: как строка источника, клик продолжает её ревью. */
export function RecentCollectionRow({ node, path, processing, menuItems, onProcess, onReview }: RecentCollectionRowProps) {
  const { counts } = node
  const progress = (() => {
    if (counts.total === 0) return <Text tone="muted" size="s">No sources yet</Text>
    if (counts.status === 'new') return <Text tone="muted" size="s">Not processed yet</Text>
    return (
      <>
        <Progress value={counts.review_fraction} />
        <span className={css.caption}><Text tone="muted" size="s">{counts.progress_caption}</Text></span>
      </>
    )
  })()
  const classes = [css.row, counts.can_review && css.clickable, counts.status === 'reviewed' && css.done].filter(Boolean).join(' ')
  const tooltip = [COLLECTION, ...(path.length ? [path.join(' / ')] : [])].join(TOOLTIP_LINE)
  return (
    <div className={classes} title={tooltip} role="option" aria-selected={false} onClick={() => { if (counts.can_review) onReview() }}>
      <span className={css.type}><Icon as={Folder} /></span>
      <div className={css.name}>
        <span className={css.title}>{node.name}</span>
        {path.length > 0 && <span className={css.path}>{path.at(-1)}</span>}
      </div>
      <div className={css.progress}>{progress}</div>
      <div className={css.action} onClick={e => e.stopPropagation()}>
        <ReviewAction
          status={counts.status}
          canProcess={counts.can_process}
          canReview={counts.can_review}
          primary={false}
          busy={processing}
          onProcess={onProcess}
          onReview={onReview}
        />
      </div>
      <div className={css.more} onClick={e => e.stopPropagation()}>
        <Menu trigger={<IconButton icon={Ellipsis} label="More" />} items={menuItems} />
      </div>
    </div>
  )
}
