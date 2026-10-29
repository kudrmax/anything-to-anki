import type { Settings } from '@/api/types'
import type { SettingsStore } from '../useSettings'

export interface SectionProps {
  store: SettingsStore
  form: Settings
}
