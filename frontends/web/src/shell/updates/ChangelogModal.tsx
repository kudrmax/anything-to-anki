import type { ReactNode } from 'react'
import type { ChangelogEntry } from '@/api/types'
import { Button, Empty, Modal, Text } from '@/ui'
import css from './ChangelogModal.module.css'

/** update — что принесёт обновление; whatsnew — что вышло с прошлого открытия; history — вся история. */
export type ChangelogMode = 'update' | 'whatsnew' | 'history'

const TITLES: Record<ChangelogMode, string> = {
  update: 'Update available',
  whatsnew: "What's new",
  history: 'Changelog',
}

interface ChangelogModalProps {
  mode: ChangelogMode
  entries: ChangelogEntry[]
  onClose: () => void
  /** Действие рядом с Close: кнопка Update в попапе обновления. */
  action?: ReactNode
  /** Строка над кнопками: например, почему обновление не началось. */
  note?: ReactNode
}

const RELEASE_DAY_FORMAT: Intl.DateTimeFormatOptions = { year: 'numeric', month: 'long', day: 'numeric' }

const releaseDay = (isoDay: string) => new Date(`${isoDay}T00:00:00`).toLocaleDateString(undefined, RELEASE_DAY_FORMAT)

export function ChangelogModal({ mode, entries, onClose, action, note }: ChangelogModalProps) {
  return (
    <Modal
      reading
      title={TITLES[mode]}
      onClose={onClose}
      footer={(
        <>
          {note}
          <Button onClick={onClose}>Close</Button>
          {action}
        </>
      )}
    >
      {entries.length === 0 && <Empty flush>No changes recorded</Empty>}
      {entries.map(entry => (
        <article key={entry.version} className={css.entry}>
          <header className={css.heading}>
            <h2 className={css.version}>{entry.version}</h2>
            <Text tone="muted" size="s">{releaseDay(entry.released_on)}</Text>
          </header>
          {entry.summary && <p className={css.summary}>{entry.summary}</p>}
          {entry.sections.map(section => (
            <section key={section.title} className={css.section}>
              <h3 className={css.sectionTitle}>{section.title}</h3>
              {/* HTML отрисован backend из CHANGELOG.md репозитория, сырой HTML там выключен. */}
              <div className={css.body} dangerouslySetInnerHTML={{ __html: section.html }} />
            </section>
          ))}
        </article>
      ))}
    </Modal>
  )
}
