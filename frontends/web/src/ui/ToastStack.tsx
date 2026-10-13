import type { ReactNode } from 'react'
import css from './ToastStack.module.css'

interface ToastStackProps {
  /** Поднять над панелью, прилипшей к низу экрана. */
  raised?: boolean
  children: ReactNode
}

/** Несколько тостов одного экрана встают друг над другом, а не в одну точку. */
export function ToastStack({ raised = false, children }: ToastStackProps) {
  return <div className={raised ? `${css.stack} ${css.raised}` : css.stack}>{children}</div>
}
