import { useState } from 'react'
import type { BookChapterPreview } from '@/api/types'
import { Button, Chip, Label, Modal, Stack } from '@/ui'
import css from './BookSplitModal.module.css'

interface BookSplitModalProps {
  bookName: string
  wordCount: number
  chapters: BookChapterPreview[]
  onCancel: () => void
  onConfirm: (split: boolean) => void
}

const words = (count: number): string => `${count.toLocaleString('en-US')} words`

const wordRange = (chapters: BookChapterPreview[]): string => {
  const counts = chapters.map(chapter => chapter.word_count)
  const min = Math.min(...counts)
  const max = Math.max(...counts)
  return min === max ? words(min) : `${min.toLocaleString('en-US')}–${words(max)}`
}

export function BookSplitModal({ bookName, wordCount, chapters, onCancel, onConfirm }: BookSplitModalProps) {
  const [split, setSplit] = useState(true)

  return (
    <Modal
      title={bookName}
      onClose={onCancel}
      footer={
        <>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          <Button variant="fill" onClick={() => onConfirm(split)}>Confirm</Button>
        </>
      }
    >
      <div>
        <Label flush>Add the book as</Label>
        <Stack>
          <Chip outlined on={split} onClick={() => setSplit(true)}>
            {chapters.length} chapters · {wordRange(chapters)} each
          </Chip>
          <Chip outlined on={!split} onClick={() => setSplit(false)}>
            One source · {words(wordCount)}
          </Chip>
        </Stack>
      </div>
      {split && (
        <div>
          <Label flush>Sources in collection «{bookName}»</Label>
          <div className={css.chapters}>
            {chapters.map((chapter, index) => (
              <div key={index} className={css.chapter}>
                <span>{chapter.title}</span>
                <span className={css.words}>{words(chapter.word_count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  )
}
