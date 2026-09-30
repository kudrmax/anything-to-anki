import { useState } from 'react'
import { nativeHost } from '@/lib/nativeHost'
import { Button, Field } from '@/ui'
import css from './PathField.module.css'

interface PathFieldProps {
  value: string
  placeholder: string
  extensions?: readonly string[]
  onChange: (path: string) => void
}

/** A file path typed by hand; inside the macOS app it can also be picked in Finder. */
export function PathField({ value, placeholder, extensions, onChange }: PathFieldProps) {
  const [host] = useState(() => nativeHost())
  const [picking, setPicking] = useState(false)

  const pick = async () => {
    if (!host) return
    setPicking(true)
    try {
      const path = await host.pickFile(extensions)
      if (path) onChange(path)
    } finally {
      setPicking(false)
    }
  }

  return (
    <div className={css.row}>
      <Field className={css.field} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
      {host && <Button busy={picking} onClick={pick}>Choose…</Button>}
    </div>
  )
}
