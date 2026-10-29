import type { ReactNode } from 'react'
import css from './ToastStack.module.css'

/** Панель, прилипшая к низу экрана, над которой встают тосты. */
export type ToastBar = 'selection' | 'decisions'

interface ToastStackProps {
  /** Поднять над этой панелью; нет — тосты у края экрана. */
  above?: ToastBar | null
  children: ReactNode
}

const ABOVE: Record<ToastBar, string> = { selection: css.aboveSelection, decisions: css.aboveDecisions }

/** Несколько тостов одного экрана встают друг над другом, а не в одну точку. */
export function ToastStack({ above = null, children }: ToastStackProps) {
  return <div className={above ? `${css.stack} ${ABOVE[above]}` : css.stack}>{children}</div>
}
