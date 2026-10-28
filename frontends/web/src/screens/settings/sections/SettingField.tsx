import type { Settings } from '@/api/types'
import { Field } from '@/ui'
import type { SettingsStore } from '../useSettings'

export type TextSetting = { [K in keyof Settings]: Settings[K] extends string ? K : never }[keyof Settings]

interface SettingFieldProps {
  store: SettingsStore
  name: TextSetting
}

/** Текст сохраняется, когда его закончили вводить: по уходу из поля или Enter. */
export function SettingField({ store, name }: SettingFieldProps) {
  return (
    <Field
      value={store.form?.[name] ?? ''}
      onChange={e => store.edit(name, e.target.value)}
      onBlur={() => void store.commit()}
      onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }}
    />
  )
}
