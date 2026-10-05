import css from './Badge.module.css'

/** Короткая метка вида карточки, прижатая к правому краю строки. */
export function Badge({ children }: { children: string }) {
  return <span className={css.badge}>{children}</span>
}
