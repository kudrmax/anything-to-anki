import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import css from './Modal.module.css'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer: ReactNode
  wide?: boolean
  /** Шире обычного, но под длину строки текста: для чтения. */
  reading?: boolean
  /** Лист снизу экрана: для телефона. */
  sheet?: boolean
}

export function Modal({ title, onClose, children, footer, wide = false, reading = false, sheet = false }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className={sheet ? `${css.overlay} ${css.sheet}` : css.overlay} onClick={onClose}>
      <div className={[css.modal, wide && css.wide, reading && css.reading].filter(Boolean).join(' ')} role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}>
        <h2 className={css.title}>{title}</h2>
        <div className={css.content}>{children}</div>
        <div className={css.footer}>{footer}</div>
      </div>
    </div>,
    document.body,
  )
}
