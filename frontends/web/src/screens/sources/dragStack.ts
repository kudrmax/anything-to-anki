import type { DragEvent } from 'react'
import css from './DragStack.module.css'

/** Тащим несколько источников: под курсором стопка из строки и счётчик, как в Finder. */
export function setStackDragImage(e: DragEvent, row: HTMLElement, count: number): void {
  const stack = document.createElement('div')
  stack.className = css.stack
  stack.setAttribute('aria-hidden', 'true')
  stack.style.setProperty('--stack-w', `${row.offsetWidth}px`)

  const top = row.cloneNode(true) as HTMLElement
  top.removeAttribute('role')
  top.removeAttribute('title')
  top.classList.add(css.top)

  const badge = document.createElement('span')
  badge.className = css.count
  badge.textContent = String(count)

  stack.append(top, badge)
  document.body.append(stack)
  const rect = row.getBoundingClientRect()
  e.dataTransfer.setDragImage(stack, e.clientX - rect.left, e.clientY - rect.top + top.offsetTop)
  setTimeout(() => stack.remove())
}
