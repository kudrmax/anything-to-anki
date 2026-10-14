// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { useState } from 'react'
import { Button, Field, Modal, TextArea } from '@/ui'
import type { Source } from './mockData'
import css from './prototype.module.css'

interface AddPartModalProps {
  source: Source
  onAdd: (title: string, text: string) => void
  onClose: () => void
}

const defaultTitle = (source: Source): string =>
  `${source.partNoun === 'Episode' ? 'Episode' : 'Part'} ${source.parts.length + 1}`

export function AddPartModal({ source, onAdd, onClose }: AddPartModalProps) {
  const [title, setTitle] = useState(() => defaultTitle(source))
  const [text, setText] = useState('')
  const [path, setPath] = useState('')
  const submit = () => {
    onAdd(title.trim() || defaultTitle(source), text)
    onClose()
  }
  return (
    <Modal
      title={`Add part to ${source.title}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="link" onClick={onClose}>Cancel</Button>
          <Button variant="fill" onClick={submit}>Add part</Button>
        </>
      }
    >
      <label className={css.fieldLabel}>
        Title
        <Field autoFocus value={title} onChange={e => setTitle(e.target.value)} />
      </label>
      <label className={css.fieldLabel}>
        Text
        <TextArea placeholder="Paste the text of the part" value={text} onChange={e => setText(e.target.value)} />
      </label>
      <label className={css.fieldLabel}>
        Or a file
        <Field placeholder="/path/to/episode.srt" value={path} onChange={e => setPath(e.target.value)} />
      </label>
    </Modal>
  )
}
