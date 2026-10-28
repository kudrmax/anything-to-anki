import type { HTMLAttributes, ReactNode } from 'react'
import type { CardElement, CardLayoutView } from '@/api/types'
import { kindOf, styleOf } from './layoutView'
import css from './cardLayout.module.css'

interface CardBlockProps extends HTMLAttributes<HTMLDivElement> {
  element: CardElement
  view: CardLayoutView
  children: ReactNode
}

/** Обёртка элемента: размер, тон, жирность, выравнивание и отступы из стиля раскладки. */
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
      data-space-top={style?.space_top}
      data-space-right={style?.space_right}
      data-space-bottom={style?.space_bottom}
      data-space-left={style?.space_left}
      {...rest}
    >
      {children}
    </div>
  )
}
