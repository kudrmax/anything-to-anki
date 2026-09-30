import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { IconButton } from '@/ui'
import css from './PageHeader.module.css'

interface PageHeaderProps {
  title: string
  /** Путь или обработчик для стрелки «назад». */
  back?: string | (() => void)
  meta?: ReactNode
  /** Действия справа. */
  children?: ReactNode
}

export function PageHeader({ title, back, meta, children }: PageHeaderProps) {
  const navigate = useNavigate()
  const goBack = () => (typeof back === 'string' ? navigate(back) : back?.())
  return (
    <div className={css.header}>
      <div className={css.lead}>
        {back !== undefined && <IconButton icon={ArrowLeft} label="Back" className={css.back} onClick={goBack} />}
        <h1 className={css.title}>{title}</h1>
        {meta && <div className={css.meta}>{meta}</div>}
      </div>
      {children}
    </div>
  )
}
