import { useState, type FormEvent } from 'react'
import { Button, Field, Modal } from '@/ui'

interface NameModalProps {
  title: string
  initial: string
  submitLabel: string
  onSubmit: (name: string) => void
  onClose: () => void
}

/** Имя коллекции из шапки области: на телефоне дерево спрятано в листе. */
export function NameModal({ title, initial, submitLabel, onSubmit, onClose }: NameModalProps) {
  const [name, setName] = useState(initial)
  const trimmed = name.trim()
  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (trimmed) onSubmit(trimmed)
  }
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="link" onClick={onClose}>Cancel</Button>
          <Button variant="fill" disabled={!trimmed} onClick={() => submit()}>{submitLabel}</Button>
        </>
      }
    >
      <form onSubmit={submit}>
        <Field autoFocus aria-label="Collection name" placeholder="Collection name" value={name} onChange={e => setName(e.target.value)} onFocus={e => e.target.select()} />
      </form>
    </Modal>
  )
}
