import css from './Spinner.module.css'

export function Spinner() {
  return <span className={css.spinner} role="status" aria-label="Loading" />
}
