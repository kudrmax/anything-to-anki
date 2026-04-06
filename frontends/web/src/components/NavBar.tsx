import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

export function NavBar() {
  return (
    <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
      <div>
        <span className="flex items-center gap-2 text-base font-semibold text-slate-100">
          <img src="/anki-logo.png" alt="Anki" className="w-7 h-7 rounded-lg object-cover" />
          Anything to Anki
        </span>
        <p className="text-xs text-slate-500 mt-0.5">Vocabulary extraction from any text</p>
      </div>
      <nav className="flex items-center gap-1">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            cn(
              'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              isActive
                ? 'text-slate-100 bg-slate-800'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-900',
            )
          }
        >
          Inbox
        </NavLink>
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cn(
              'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              isActive
                ? 'text-slate-100 bg-slate-800'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-900',
            )
          }
        >
          Settings
        </NavLink>
      </nav>
    </header>
  )
}
