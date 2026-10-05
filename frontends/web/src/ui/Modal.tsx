import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import css from './Modal.module.css'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer: ReactNode
  wide?: boolean
}

export function Modal({ title, onClose, children, footer, wide = false }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className={css.overlay} onClick={onClose}>
      <div className={wide ? `${css.modal} ${css.wide}` : css.modal} role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}>
        <h2 className={css.title}>{title}</h2>
        <div className={css.content}>{children}</div>
        <div className={css.footer}>{footer}</div>
      </div>
    </div>,
    document.body,
  )
}
