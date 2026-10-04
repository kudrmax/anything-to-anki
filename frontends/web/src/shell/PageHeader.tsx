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
  /** На узком экране мета уходит из строки заголовка в ряд с действиями. */
  metaWithActions?: boolean
}

export function PageHeader({ title, back, meta, children, metaWithActions = false }: PageHeaderProps) {
  const navigate = useNavigate()
  const goBack = () => (typeof back === 'string' ? navigate(back) : back?.())
  return (
    <div className={metaWithActions ? `${css.header} ${css.metaWithActions}` : css.header}>
      <div className={css.lead}>
        <div className={css.heading}>
          {back !== undefined && <IconButton icon={ArrowLeft} label="Back" className={css.back} onClick={goBack} />}
          <h1 className={css.title}>{title}</h1>
        </div>
        {meta && <div className={css.meta}>{meta}</div>}
      </div>
      {children}
    </div>
  )
}
