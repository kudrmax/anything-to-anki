import css from './Kbd.module.css'

/** `corner` — подпись в углу иконки: кнопка остаётся одной иконкой. */
export function Kbd({ children, corner = false }: { children: string; corner?: boolean }) {
  return <kbd className={corner ? `${css.kbd} ${css.corner}` : css.kbd}>{children}</kbd>
}
