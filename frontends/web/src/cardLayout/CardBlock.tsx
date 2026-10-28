import type { HTMLAttributes, ReactNode } from 'react'
import type { CardElement, CardLayoutView } from '@/api/types'
import { kindOf, styleOf } from './layoutView'
import css from './cardLayout.module.css'

interface CardBlockProps extends HTMLAttributes<HTMLDivElement> {
  element: CardElement
  view: CardLayoutView
  children: ReactNode
}

/** Обёртка элемента: размер, тон, жирность и выравнивание из стиля раскладки. */
export function CardBlock({ element, view, children, className, ...rest }: CardBlockProps) {
  const style = styleOf(view, element)
  return (
    <div
      className={className ? `${css.block} ${className}` : css.block}
      data-element={element}
      data-kind={kindOf(view, element)}
      data-size={style?.size}
      data-tone={style?.tone}
      data-bold={style?.bold}
      data-align={style?.align}
      data-valign={style?.valign}
      {...rest}
    >
      {children}
    </div>
  )
}
