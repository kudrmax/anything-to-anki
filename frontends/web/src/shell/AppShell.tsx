import { Outlet } from 'react-router-dom'
import '@/styles/base.css'
import { useApplyTheme } from '@/lib/theme'
import { Rail } from './Rail'
import css from './AppShell.module.css'

export function AppShell() {
  useApplyTheme()
  return (
    <div className={css.shell}>
      <Rail />
      <main className={css.main}>
        <Outlet />
      </main>
    </div>
  )
}
