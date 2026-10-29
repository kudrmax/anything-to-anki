import css from './Tag.module.css'

/** Мелкий факт рядом с названием: формат файла, кодек, число слов. Каждый факт — своя метка. */
export function Tag({ children }: { children: string }) {
  return <span className={css.tag}>{children}</span>
}
