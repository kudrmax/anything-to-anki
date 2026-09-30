import css from './Toast.module.css'

interface ToastProps {
  message: string | null
  tone?: 'info' | 'warn'
}

export function Toast({ message, tone = 'info' }: ToastProps) {
  if (!message) return null
  return <div className={tone === 'warn' ? `${css.toast} ${css.warn}` : css.toast} role="status">{message}</div>
}
