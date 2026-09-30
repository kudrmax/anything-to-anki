import css from './Kbd.module.css'

export function Kbd({ children }: { children: string }) {
  return <kbd className={css.kbd}>{children}</kbd>
}
