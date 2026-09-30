import { Outlet } from 'react-router-dom'
import '@/styles/base.css'
import { useTheme } from '@/lib/theme'
import { Rail } from './Rail'
import css from './AppShell.module.css'

export function AppShell() {
  useTheme()
  return (
    <div className={css.shell}>
      <Rail />
      <main className={css.main}>
        <Outlet />
      </main>
    </div>
  )
}
