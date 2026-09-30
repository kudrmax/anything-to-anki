import type { LucideIcon } from 'lucide-react'
import css from './Icon.module.css'

interface IconProps {
  as: LucideIcon
  size?: 'm' | 's'
}

export function Icon({ as: Glyph, size = 'm' }: IconProps) {
  return <Glyph className={size === 's' ? css.small : css.icon} aria-hidden />
}
