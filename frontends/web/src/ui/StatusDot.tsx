import css from './StatusDot.module.css'

export type Tone = 'idle' | 'ok' | 'accent' | 'warn' | 'err' | 'off' | 'run'

export function StatusDot({ tone = 'idle' }: { tone?: Tone }) {
  return <span className={`${css.dot} ${css[tone]}`} />
}
