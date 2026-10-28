import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { Icon, Spinner, Text } from '@/ui'
import css from './settings.module.css'

const SHOWN_MS = 2000

interface SaveStatusProps {
  saving: boolean
  savedAt: number | null
  error: string | null
}

/** Настройки сохраняются сами: здесь видно, что изменение дошло или почему нет. */
export function SaveStatus({ saving, savedAt, error }: SaveStatusProps) {
  const [faded, setFaded] = useState<number | null>(null)
  useEffect(() => {
    if (savedAt === null) return
    const timer = setTimeout(() => setFaded(savedAt), SHOWN_MS)
    return () => clearTimeout(timer)
  }, [savedAt])
  const fresh = savedAt !== null && savedAt !== faded

  if (error) return <span className={css.status}><Text tone="err" size="s">Not saved: {error}</Text></span>
  if (saving) return <span className={css.status}><Spinner /></span>
  if (fresh) return <span className={css.status}><Icon as={Check} size="s" /><Text tone="muted" size="s">Saved</Text></span>
  return null
}
